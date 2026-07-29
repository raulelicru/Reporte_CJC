"""Motor de analítica avanzada de estrategia (Fase A del roadmap elite).

Todo se calcula desde el IngestResult ya normalizado (toques + pagos + cartera),
sin insumos externos. Incluye la pieza metodológica clave: la corrección del
sesgo de truncamiento vía panel dama-día (hazard en tiempo discreto).

Piezas:
  - universo evaluable (excluye quien pagó antes de la ventana de gestión)
  - diagnóstico de truncamiento: curva ingenua (sesgada) vs. hazard corregido
  - curva dosis-respuesta sobre el panel
  - esfuerzo-vs-retorno por temporalidad + escenario de reasignación
  - heatmap de contactabilidad día-de-semana × hora (usa la hora de los crudos)
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .attribution import (
    Payment,
    Touch,
    attribute_all,
    dif_dias,
)
from .brands import DEFAULT_BRAND, temp_rank

DOW = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

# Costo unitario por defecto (pesos) — editable en la app. Son supuestos
# conservadores de mercado; el retorno se recalcula al cambiarlos en pantalla.
COSTOS_DEFAULT = {
    "Llamada": 8.0,     # por gestión humana (tiempo de agente)
    "IVR": 0.45,        # por intento de marcación automática
    "SMS": 0.28,        # por mensaje enviado
    "marcador_min": 0.35,  # por minuto de marcador (C3)
}


def _daterange(a: str, b: str):
    d0, d1 = date.fromisoformat(a), date.fromisoformat(b)
    cur = d0
    while cur <= d1:
        yield cur.isoformat()
        cur += timedelta(days=1)


def compute_estrategia(ing, brand=None, lookback: int = 2) -> dict[str, Any]:
    brand = brand or DEFAULT_BRAND

    inicio = ing.profile.get("fecha_liberacion")
    corte = ing.profile.get("fecha_corte_datos")
    dias_canal = sorted({t["dia"] for t in ing.toques})
    if not inicio and dias_canal:
        inicio = dias_canal[0]
    if not corte and dias_canal:
        corte = dias_canal[-1]
    if not inicio or not corte:
        return {"disponible": False}

    saldo = {c["num_dama"]: c["saldo_cobro"] for c in ing.cartera}
    damas = list(saldo.keys())

    # Primer pago y recuperado por dama.
    pago_dia: dict[int, str] = {}
    recup: dict[int, float] = {}
    for p in ing.pagos:
        if p["fecha_pago"] and p["recuperado"] > 0:
            if p["num_dama"] not in pago_dia or p["fecha_pago"] < pago_dia[p["num_dama"]]:
                pago_dia[p["num_dama"]] = p["fecha_pago"]
            recup[p["num_dama"]] = recup.get(p["num_dama"], 0.0) + p["recuperado"]

    # Temporalidad por dama (última conocida en gestiones).
    temp_dama: dict[int, str] = {}
    for g in ing.gestiones:
        if g.get("temp"):
            temp_dama[g["num_dama"]] = g["temp"]

    # Toques efectivos por dama (ordenados) para el panel.
    ef_por_dama: dict[int, list[dict]] = {}
    for t in ing.toques:
        if t["efectivo"]:
            ef_por_dama.setdefault(t["num_dama"], []).append(t)
    for arr in ef_por_dama.values():
        arr.sort(key=lambda t: t["dia"])

    # ── Universo evaluable: excluir quien pagó ANTES del inicio de ventana ──
    evaluables, pre_ventana, monto_pre = [], 0, 0.0
    for d in damas:
        pd_ = pago_dia.get(d)
        if pd_ and pd_ < inicio:
            pre_ventana += 1
            monto_pre += recup.get(d, 0.0)
        else:
            evaluables.append(d)

    # ── Diagnóstico de truncamiento (curva INGENUA, por dama, sesgada) ──
    naive = _curva_ingenua(evaluables, ef_por_dama, pago_dia)

    # ── Panel dama-día (hazard) → curva dosis-respuesta CORREGIDA ──
    panel = _panel(evaluables, ef_por_dama, pago_dia, inicio, corte, lookback)
    corregida = _hazard_por_dosis(panel)
    hazard_canal = _hazard_por_canal(panel)

    # ── Esfuerzo vs. retorno por temporalidad + reasignación ──
    esfuerzo = _esfuerzo_retorno(evaluables, ef_por_dama, recup, temp_dama, brand)
    reasignacion = _reasignacion(esfuerzo)

    # ── Timing: día de semana × hora (contactabilidad) ──
    timing = _timing(ing.toques)

    # ── Modelos (Fase B) ──
    promesa_dama = {g["num_dama"] for g in ing.gestiones if g.get("promesa_fecha")}
    modelos = compute_modelos(evaluables, ef_por_dama, pago_dia, recup, temp_dama,
                              saldo, promesa_dama, brand, panel)

    # ── Segmentación (k-means) + correlación (palancas) ──
    segmentacion = _segmentacion(evaluables, ef_por_dama, pago_dia, recup, temp_dama,
                                 saldo, promesa_dama, brand)
    correlacion = _correlacion(evaluables, ef_por_dama, pago_dia, recup, temp_dama,
                               saldo, promesa_dama, brand)

    # ── ROI en pesos por canal (costos por defecto; editable en la app) ──
    roi = _roi(ing, brand)

    return {
        "disponible": True,
        "ventana": {"inicio": inicio, "corte": corte, "lookback": lookback},
        "universo": {
            "damas_cartera": len(damas), "evaluables": len(evaluables),
            "pre_ventana_excluidas": pre_ventana, "monto_pre_ventana": monto_pre,
        },
        "truncamiento": {"ingenua": naive, "corregida": corregida},
        "hazard_canal": hazard_canal,
        "esfuerzo_retorno": esfuerzo,
        "reasignacion": reasignacion,
        "timing": timing,
        "modelos": modelos,
        "segmentacion": segmentacion,
        "correlacion": correlacion,
        "roi": roi,
        # Mapa temporalidad por dama (para roll-rate entre snapshots).
        "temp_por_dama": {str(d): temp_dama[d] for d in evaluables if d in temp_dama},
    }


def _curva_ingenua(evaluables, ef_por_dama, pago_dia):
    """Tasa de pago por nº total de gestiones efectivas por dama (SESGADA)."""
    buckets: dict[str, dict] = {}
    def key(n):
        return "0" if n == 0 else "1" if n == 1 else "2-3" if n <= 3 else "4-7" if n <= 7 else "8+"
    for d in evaluables:
        n = len(ef_por_dama.get(d, []))
        pago = 1 if d in pago_dia else 0
        b = buckets.setdefault(key(n), {"damas": 0, "pagos": 0})
        b["damas"] += 1
        b["pagos"] += pago
    orden = ["0", "1", "2-3", "4-7", "8+"]
    return [{"bucket": k, "damas": buckets[k]["damas"], "tasa": buckets[k]["pagos"] / buckets[k]["damas"]}
            for k in orden if k in buckets]


def _panel(evaluables, ef_por_dama, pago_dia, inicio, corte, lookback):
    """Panel dama-día: una fila por día en riesgo. Evento = pagó exactamente ese día."""
    filas = []
    dias = list(_daterange(inicio, corte))
    for d in evaluables:
        toques = ef_por_dama.get(d, [])
        pd_ = pago_dia.get(d)
        for D in dias:
            if pd_ and pd_ < D:
                break  # ya pagó: sale del panel
            pago_hoy = 1 if pd_ == D else 0
            # dosis previa: toques efectivos con día < D
            dosis_prev = sum(1 for t in toques if t["dia"] < D)
            # exposición por canal en [D-lookback, D]
            canales = set()
            for t in toques:
                delta = dif_dias(D, t["dia"])
                if 0 <= delta <= lookback:
                    canales.add(t["canal"])
            filas.append({"dosis_prev": dosis_prev, "pago": pago_hoy,
                          "Llamada": int("Llamada" in canales), "IVR": int("IVR" in canales),
                          "SMS": int("SMS" in canales), "expuesto": int(bool(canales))})
            if pago_hoy:
                break
    return filas


def _hazard_por_dosis(panel):
    """Hazard (P(pago|en riesgo)) por dosis acumulada previa — curva CORREGIDA."""
    def key(n):
        return "0" if n == 0 else "1" if n == 1 else "2-3" if n <= 3 else "4-7" if n <= 7 else "8+"
    acc: dict[str, dict] = {}
    for f in panel:
        b = acc.setdefault(key(f["dosis_prev"]), {"filas": 0, "pagos": 0})
        b["filas"] += 1
        b["pagos"] += f["pago"]
    orden = ["0", "1", "2-3", "4-7", "8+"]
    return [{"bucket": k, "dias_riesgo": acc[k]["filas"], "hazard": acc[k]["pagos"] / acc[k]["filas"]}
            for k in orden if k in acc]


def _hazard_por_canal(panel):
    """Hazard con vs sin exposición a cada canal en la ventana de lookback."""
    out = []
    for canal in ["Llamada", "IVR", "SMS"]:
        con = [f for f in panel if f[canal]]
        sin = [f for f in panel if not f[canal]]
        hc = sum(f["pago"] for f in con) / len(con) if con else 0.0
        hs = sum(f["pago"] for f in sin) / len(sin) if sin else 0.0
        out.append({"canal": canal, "hazard_con": hc, "hazard_sin": hs,
                    "lift": (hc - hs), "dias_con": len(con)})
    return out


def _esfuerzo_retorno(evaluables, ef_por_dama, recup, temp_dama, brand):
    """Por temporalidad: esfuerzo (gestiones), retorno (recuperado) y eficiencia."""
    acc: dict[str, dict] = {}
    for d in evaluables:
        temp = temp_dama.get(d) or "Sin tramo"
        n = len(ef_por_dama.get(d, []))
        r = recup.get(d, 0.0)
        b = acc.setdefault(temp, {"gestiones": 0, "recuperado": 0.0, "damas": 0, "pagadoras": 0})
        b["gestiones"] += n
        b["recuperado"] += r
        b["damas"] += 1
        if r > 0:
            b["pagadoras"] += 1
    tot_g = sum(b["gestiones"] for b in acc.values()) or 1
    tot_r = sum(b["recuperado"] for b in acc.values()) or 1
    filas = [{
        "temp": t, "gestiones": b["gestiones"], "pct_esfuerzo": b["gestiones"] / tot_g,
        "recuperado": b["recuperado"], "pct_recuperado": b["recuperado"] / tot_r,
        "damas": b["damas"], "pagadoras": b["pagadoras"],
        "gestiones_por_pago": (b["gestiones"] / b["pagadoras"]) if b["pagadoras"] else None,
        "pesos_por_gestion": (b["recuperado"] / b["gestiones"]) if b["gestiones"] else 0.0,
    } for t, b in acc.items()]
    # Orden por severidad de la marca (los que no estén, al final por saldo).
    filas.sort(key=lambda x: (temp_rank(brand, x["temp"]) if temp_rank(brand, x["temp"]) >= 0 else 99))
    return filas


def _reasignacion(esfuerzo, eficiencia_receptor=0.35):
    """Mueve capacidad del tramo menos eficiente al más eficiente (supuestos pesimistas)."""
    candidatos = [e for e in esfuerzo if e["gestiones"] > 0 and e["temp"] != "Sin tramo"]
    if len(candidatos) < 2:
        return None
    peor = min(candidatos, key=lambda e: e["pesos_por_gestion"])
    mejor = max(candidatos, key=lambda e: e["pesos_por_gestion"])
    if peor["temp"] == mejor["temp"]:
        return None
    gestiones_liberadas = peor["gestiones"]
    total_g = sum(e["gestiones"] for e in esfuerzo) or 1
    sacrificada = peor["recuperado"]  # se pierde TODA la recuperación del esfuerzo retirado
    adicional = gestiones_liberadas * mejor["pesos_por_gestion"] * eficiencia_receptor
    neto = adicional - sacrificada
    total_r = sum(e["recuperado"] for e in esfuerzo) or 1
    return {
        "peor": peor["temp"], "mejor": mejor["temp"],
        "gestiones_liberadas": gestiones_liberadas, "pct_capacidad": gestiones_liberadas / total_g,
        "sacrificada": sacrificada, "adicional": adicional, "neto": neto,
        "neto_pct": neto / total_r, "eficiencia_receptor": eficiencia_receptor,
    }


FEATURE_NAMES = ["gestiones", "llamadas", "ivr", "sms", "dias_tocados", "promesa", "saldo", "temp_rank"]
FEATURE_LABELS = {
    "gestiones": "Gestiones", "llamadas": "Llamadas", "ivr": "IVR", "sms": "SMS",
    "dias_tocados": "Días tocados", "promesa": "Promesa", "saldo": "Saldo",
    "temp_rank": "Severidad tramo", "pago": "Pagó",
}


def _features_por_dama(evaluables, ef_por_dama, pago_dia, recup, temp_dama, saldo, promesa_dama, brand):
    """Matriz de features por dama (compartida por modelos, segmentación y correlación)."""
    import numpy as np
    feats, ys, rs, ids = [], [], [], []
    for d in evaluables:
        toques = ef_por_dama.get(d, [])
        nll = sum(1 for t in toques if t["canal"] == "Llamada")
        niv = sum(1 for t in toques if t["canal"] == "IVR")
        nsm = sum(1 for t in toques if t["canal"] == "SMS")
        dias = len({t["dia"] for t in toques})
        tr = temp_rank(brand, temp_dama.get(d))
        feats.append([len(toques), nll, niv, nsm, dias, int(d in promesa_dama),
                      float(saldo.get(d, 0.0)), tr if tr >= 0 else 0])
        ys.append(1 if d in pago_dia else 0)
        rs.append(float(recup.get(d, 0.0)))
        ids.append(d)
    return np.array(feats, float), np.array(ys), np.array(rs, float), ids


def compute_modelos(evaluables, ef_por_dama, pago_dia, recup, temp_dama, saldo,
                    promesa_dama, brand, panel) -> dict:
    """Modelos (Fase B): logístico sobre el panel (efectos), logístico por dama
    (scoring/deciles) y árbol con TASAS REALES por hoja. Guarda ante datos pobres."""
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.tree import DecisionTreeClassifier
        from sklearn.metrics import roc_auc_score
    except Exception:
        return {"disponible": False, "motivo": "sklearn no disponible"}

    out: dict = {"disponible": True}

    # ── (a) Logístico sobre el PANEL (válido para efectos, a igual día de riesgo) ──
    if len(panel) >= 200:
        Xp = np.array([[f["dosis_prev"], f["Llamada"], f["IVR"], f["SMS"]] for f in panel], float)
        yp = np.array([f["pago"] for f in panel])
        if yp.sum() >= 10 and (yp == 0).sum() >= 10:
            m = LogisticRegression(class_weight="balanced", max_iter=1000)
            m.fit(Xp, yp)
            try:
                auc = float(roc_auc_score(yp, m.predict_proba(Xp)[:, 1]))
            except Exception:
                auc = None
            nombres = ["Dosis previa (+1)", "Llamada en ventana", "IVR en ventana", "SMS en ventana"]
            out["panel"] = {"auc": auc, "n": len(panel),
                            "odds": [{"var": n, "or": float(np.exp(c))}
                                     for n, c in zip(nombres, m.coef_[0])]}

    # ── Matriz de features por dama (para scoring/deciles/árbol) ──
    FN = FEATURE_NAMES
    X, y, _r, ids = _features_por_dama(evaluables, ef_por_dama, pago_dia, recup, temp_dama, saldo, promesa_dama, brand)

    if len(y) >= 100 and y.sum() >= 20 and (y == 0).sum() >= 20:
        # ── (b) Logístico por dama → deciles con esfuerzo aplicado ──
        md = LogisticRegression(class_weight="balanced", max_iter=1000)
        md.fit(X, y)
        proba = md.predict_proba(X)[:, 1]
        try:
            out["dama_auc"] = float(roc_auc_score(y, proba))
        except Exception:
            out["dama_auc"] = None
        orden = np.argsort(-proba)
        deciles = []
        n = len(orden)
        for k in range(10):
            idx = orden[int(k * n / 10):int((k + 1) * n / 10)]
            if len(idx) == 0:
                continue
            deciles.append({"decil": k + 1, "damas": int(len(idx)),
                            "tasa_pago": float(y[idx].mean()),
                            "gestiones_prom": float(X[idx, 0].mean())})
        out["deciles"] = deciles

        # ── (c) Árbol (depth 3) con TASAS REALES por hoja ──
        tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=max(50, len(y) // 40),
                                      class_weight="balanced", random_state=0)
        tree.fit(X, y)
        out["arbol"] = _reglas_arbol(tree, FN, X, y)

    return out


def _reglas_arbol(tree, feat_names, X, y):
    """Extrae reglas por hoja con la tasa de pago REAL (no la balanceada de tree_.value)."""
    import numpy as np
    t = tree.tree_
    hojas = tree.apply(X)
    reglas = []

    def recorre(nodo, cond):
        if t.children_left[nodo] == t.children_right[nodo]:  # hoja
            mask = hojas == nodo
            n = int(mask.sum())
            if n == 0:
                return
            reglas.append({"condiciones": cond, "n": n, "tasa_real": float(y[mask].mean())})
            return
        f = feat_names[t.feature[nodo]]
        thr = float(t.threshold[nodo])
        recorre(t.children_left[nodo], cond + [f"{f} ≤ {thr:.1f}"])
        recorre(t.children_right[nodo], cond + [f"{f} > {thr:.1f}"])

    recorre(0, [])
    reglas.sort(key=lambda r: -r["tasa_real"])
    return reglas


def _segmentacion(evaluables, ef_por_dama, pago_dia, recup, temp_dama, saldo,
                  promesa_dama, brand, k: int = 5) -> dict:
    """K-means (k=5) sobre features estandarizadas → perfil accionable por cluster.

    No usa el resultado (pago) para segmentar: agrupa por PERFIL de gestión/saldo
    y luego describe cada grupo con su tasa de pago real. Guarda si hay pocos datos.
    """
    try:
        import numpy as np
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
    except Exception:
        return {"disponible": False, "motivo": "sklearn no disponible"}

    X, y, r, ids = _features_por_dama(evaluables, ef_por_dama, pago_dia, recup, temp_dama, saldo, promesa_dama, brand)
    n = len(ids)
    if n < max(50, k * 10):
        return {"disponible": False, "motivo": f"universo insuficiente ({n} damas) para {k} segmentos"}

    Xs = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=k, n_init=10, random_state=0)
    lab = km.fit_predict(Xs)

    seg = []
    for c in range(k):
        m = lab == c
        cnt = int(m.sum())
        if cnt == 0:
            continue
        # tramo dominante del cluster
        tramos: dict[str, int] = {}
        for d in (ids[i] for i in range(n) if m[i]):
            tr = temp_dama.get(d)
            if tr:
                tramos[tr] = tramos.get(tr, 0) + 1
        dom = max(tramos, key=tramos.get) if tramos else "Sin tramo"
        seg.append({
            "cluster": c, "damas": cnt, "pct": cnt / n,
            "gestiones_prom": float(X[m, 0].mean()),
            "llamadas_prom": float(X[m, 1].mean()),
            "ivr_prom": float(X[m, 2].mean()),
            "sms_prom": float(X[m, 3].mean()),
            "saldo_prom": float(X[m, 6].mean()),
            "promesa_pct": float(X[m, 5].mean()),
            "tasa_pago": float(y[m].mean()),
            "recuperado": float(r[m].sum()),
            "recuperado_prom": float(r[m].mean()),
            "tramo_dominante": dom,
        })
    seg.sort(key=lambda s: -s["tasa_pago"])
    # Etiqueta legible por posición relativa (mejor/peor respuesta).
    for i, s in enumerate(seg):
        s["etiqueta"] = f"Segmento {i + 1}"
    return {"disponible": True, "k": k, "n": n, "segmentos": seg}


def _correlacion(evaluables, ef_por_dama, pago_dia, recup, temp_dama, saldo,
                 promesa_dama, brand) -> dict:
    """Matriz de correlación (Pearson) entre features + resultado (pago).

    Señala qué palancas se mueven juntas y cuáles se asocian al pago — sin
    afirmar causalidad (eso lo resuelve el panel hazard). Guarda si hay poco dato.
    """
    try:
        import numpy as np
    except Exception:
        return {"disponible": False, "motivo": "numpy no disponible"}

    X, y, r, ids = _features_por_dama(evaluables, ef_por_dama, pago_dia, recup, temp_dama, saldo, promesa_dama, brand)
    if len(ids) < 30:
        return {"disponible": False, "motivo": f"universo insuficiente ({len(ids)} damas)"}

    cols = FEATURE_NAMES + ["pago"]
    M = np.column_stack([X, y.astype(float)])
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.corrcoef(M, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0)  # columnas constantes → 0

    matriz = [[float(corr[i, j]) for j in range(len(cols))] for i in range(len(cols))]
    labels = [FEATURE_LABELS.get(c, c) for c in cols]
    # Top asociaciones con el pago (excluye la diagonal pago-pago).
    ip = cols.index("pago")
    con_pago = sorted(
        ({"var": FEATURE_LABELS.get(cols[j], cols[j]), "r": float(corr[ip, j])}
         for j in range(len(cols)) if j != ip),
        key=lambda x: -abs(x["r"]),
    )
    return {"disponible": True, "labels": labels, "cols": cols, "matriz": matriz, "con_pago": con_pago}


def _roi(ing, brand, costos: dict | None = None) -> dict:
    """ROI en pesos por canal: recuperación atribuida (last-touch) vs. costo.

    Costo = volumen de toques × costo unitario (editable) + costo del marcador
    (C3). El retorno neto es recuperado_atribuido − costo. Es una foto con
    supuestos explícitos, no una verdad contable.
    """
    costos = {**COSTOS_DEFAULT, **(costos or {})}

    # Volúmenes: intentos (todos los toques) por canal — es lo que se paga.
    intentos = {"Llamada": 0, "IVR": 0, "SMS": 0}
    efectivos = {"Llamada": 0, "IVR": 0, "SMS": 0}
    for t in ing.toques:
        c = t["canal"]
        if c in intentos:
            intentos[c] += 1
            if t["efectivo"]:
                efectivos[c] += 1

    # Recuperación atribuida por canal (modelo primario last-touch).
    pays, seen = [], set()
    for p in ing.pagos:
        if p.get("fecha_pago") and p.get("recuperado", 0) > 0:
            pays.append(Payment(dama_deuda=p["dama_deuda"], num_dama=p["num_dama"],
                                fecha_pago=p["fecha_pago"], recuperado=p["recuperado"]))
    touches = [Touch(num_dama=t["num_dama"], canal=t["canal"], dia=t["dia"],
                     efectivo=t["efectivo"], meta=t.get("meta") or {}) for t in ing.toques]
    corte = ing.profile.get("fecha_corte_datos")
    atribs = attribute_all(pays, touches, corte)
    recup_canal = {"Llamada": 0.0, "IVR": 0.0, "SMS": 0.0}
    for a in atribs:
        if a.canal in recup_canal:
            recup_canal[a.canal] += a.payment.recuperado

    # Minutos del marcador automático (C3) — el costo se aplica al recalcular.
    marc = ing.profile.get("costo_marcador") or {}
    marcador_min = float(marc.get("minutos", 0.0))

    # Volúmenes crudos: la app puede recalcular el ROI con otros costos sin re-ingerir.
    volumenes = {
        "intentos": intentos, "efectivos": efectivos, "recuperado": recup_canal,
        "marcador_min": marcador_min,
    }
    return {**roi_recompute(volumenes, costos), "volumenes": volumenes}


def roi_recompute(volumenes: dict, costos: dict | None = None) -> dict:
    """Recalcula el ROI desde los volúmenes crudos guardados + costos unitarios.

    Permite mover los costos en pantalla sin re-procesar los .xlsx."""
    costos = {**COSTOS_DEFAULT, **(costos or {})}
    intentos = volumenes["intentos"]
    efectivos = volumenes["efectivos"]
    recup_canal = volumenes["recuperado"]
    costo_marcador = float(volumenes.get("marcador_min", 0.0)) * costos["marcador_min"]

    filas = []
    for c in ("Llamada", "IVR", "SMS"):
        costo = intentos.get(c, 0) * costos[c]
        if c == "Llamada":
            costo += costo_marcador  # el marcador alimenta el canal Llamada (C2/C3)
        rec = recup_canal.get(c, 0.0)
        filas.append({
            "canal": c, "intentos": intentos.get(c, 0), "efectivos": efectivos.get(c, 0),
            "costo_unitario": costos[c], "costo": costo, "recuperado": rec,
            "neto": rec - costo, "roi": (rec / costo) if costo > 0 else None,
            "costo_por_peso": (costo / rec) if rec > 0 else None,
        })
    tot_costo = sum(f["costo"] for f in filas)
    tot_rec = sum(f["recuperado"] for f in filas)
    return {
        "disponible": True, "costos": costos, "filas": filas,
        "costo_total": tot_costo, "recuperado_total": tot_rec,
        "neto_total": tot_rec - tot_costo,
        "roi_total": (tot_rec / tot_costo) if tot_costo > 0 else None,
        "costo_marcador": costo_marcador,
    }


def roll_rate(temp_prev: dict, temp_cur: dict, brand) -> dict:
    """Matriz de transición de temporalidad entre dos snapshots (roll-rate)."""
    if not temp_prev or not temp_cur:
        return {"disponible": False}
    tramos = list(brand.temporalidades)
    comunes = set(temp_prev) & set(temp_cur)
    if not comunes:
        return {"disponible": False}
    matriz = {a: {b: 0 for b in tramos + ["(otro)"]} for a in tramos + ["(otro)"]}
    for d in comunes:
        a = temp_prev[d] if temp_prev[d] in tramos else "(otro)"
        b = temp_cur[d] if temp_cur[d] in tramos else "(otro)"
        matriz[a][b] += 1
    filas = []
    for a in tramos + ["(otro)"]:
        total = sum(matriz[a].values())
        if total == 0:
            continue
        filas.append({"desde": a, "total": total,
                      "destinos": [{"hacia": b, "n": matriz[a][b], "pct": matriz[a][b] / total}
                                   for b in tramos + ["(otro)"] if matriz[a][b] > 0]})
    return {"disponible": True, "filas": filas, "damas": len(comunes)}


def _timing(toques):
    """Heatmap día-de-semana × hora de contactabilidad (canales con hora: Llamada/IVR)."""
    grid: dict[tuple[int, int], dict] = {}
    horas_presentes = False
    for t in toques:
        if t["canal"] == "SMS":
            continue  # SMS es envío, no "contacto por hora"
        hora = (t.get("meta") or {}).get("hora")
        if hora is None:
            continue
        horas_presentes = True
        dow = date.fromisoformat(t["dia"]).weekday()
        cell = grid.setdefault((dow, hora), {"toques": 0, "efectivos": 0})
        cell["toques"] += 1
        cell["efectivos"] += 1 if t["efectivo"] else 0
    if not horas_presentes:
        return {"disponible": False}
    celdas = [{"dow": dow, "dow_lbl": DOW[dow], "hora": h, "toques": v["toques"],
               "efectivos": v["efectivos"], "tasa": v["efectivos"] / v["toques"] if v["toques"] else 0.0}
              for (dow, h), v in grid.items()]
    # Mejor franja por tasa (con volumen mínimo).
    con_vol = [c for c in celdas if c["toques"] >= 20]
    mejor = max(con_vol, key=lambda c: c["tasa"]) if con_vol else None
    return {"disponible": True, "celdas": celdas, "mejor": mejor}
