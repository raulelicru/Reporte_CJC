"""Generador del informe HTML autocontenido (Fase 7 del prompt maestro).

Un solo .html, sin dependencias externas salvo una fuente web opcional. Datos
embebidos como `const DATA`, gráficos en SVG inline, navegación pegajosa con
IntersectionObserver, respeta prefers-reduced-motion y foco de teclado.

Sistema visual PROPIO (no reusa el de la app): ink oscuro editorial + rampa de
antigüedad como dispositivo repetido, tipografía display/serif + mono tabular.
"""
from __future__ import annotations

import html
import json
from typing import Any

# ── Paleta (rampa de antigüedad = la tesis convertida en color) ──
INK, INK2, PAPER, CARD = "#10192B", "#1B2942", "#F6F7F9", "#FFFFFF"
TEXT, MUTED, LINE = "#14202F", "#5C6B80", "#DFE5EC"
RAMP = ["#0E9F6E", "#5FA88A", "#D9A21B", "#E2703A", "#B3312C", "#8A94A3"]
SIGNAL = "#2B5FD9"
CANAL_COL = {"Llamada": "#D9A21B", "IVR": "#E2703A", "SMS": "#0E9F6E", "Espontaneo": "#8A94A3"}


def _money(n):
    n = n or 0
    if abs(n) >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"${n/1_000:.0f}k"
    return f"${n:,.0f}"


def _pct(n, d=1):
    return f"{(n or 0)*100:.{d}f}%"


def _num(n):
    return f"{(n or 0):,.0f}"


def _esc(s):
    return html.escape(str(s))


# ── Bloques SVG (paleta del informe) ─────────────────────────────────────────
def _bars(items, unit="", h=None):
    """items = [{label, value, color, right}]. Barras HTML."""
    if not items:
        return '<p class="muted">Sin datos.</p>'
    mx = max([1e-9] + [i["value"] for i in items])
    rows = []
    for it in items:
        w = max(1.5, it["value"] / mx * 100)
        rows.append(
            f'<div class="bar"><span class="bl">{_esc(it["label"])}</span>'
            f'<span class="bt"><span class="bf" style="width:{w:.1f}%;background:{it.get("color", SIGNAL)}"></span></span>'
            f'<span class="br mono">{_esc(it["right"])}</span></div>')
    return "".join(rows)


def _mirror(rows):
    """Barras espejo: esfuerzo vs dinero por tramo. El elemento firma."""
    if not rows:
        return ""
    mx = max([1e-9] + [max(r["pct_esfuerzo"], r["pct_recuperado"]) for r in rows])
    out = ['<div class="mirror"><div class="mh"><span>% del esfuerzo</span><span>Tramo</span><span>% del dinero</span></div>']
    for i, r in enumerate(rows):
        c = RAMP[i % len(RAMP)]
        lw = r["pct_esfuerzo"] / mx * 100
        rw = r["pct_recuperado"] / mx * 100
        out.append(
            f'<div class="mr"><div class="ml"><span class="mb" style="width:{lw:.1f}%;background:{c};opacity:.55"></span></div>'
            f'<div class="mt">{_esc(r["temp"])}</div>'
            f'<div class="mrr"><span class="mb" style="width:{rw:.1f}%;background:{c}"></span></div></div>')
    out.append("</div>")
    return "".join(out)


def _svg_line(series, labels, fmt=lambda v: f"{v*100:.0f}%", height=200):
    """Líneas SVG multi-serie. series=[{nombre,color,puntos}]."""
    if not labels:
        return '<p class="muted">Sin datos.</p>'
    w = max(420, len(labels) * 90)
    pt, pb, pl, pr = 14, 30, 44, 14
    iw, ih = w - pl - pr, height - pt - pb
    allv = [v for s in series for v in s["puntos"]]
    mx, mn = max([1e-9] + allv), min([0.0] + allv)
    n = len(labels)
    X = lambda i: pl + (iw / 2 if n == 1 else i / (n - 1) * iw)
    Y = lambda v: pt + ih - (v - mn) / (mx - mn or 1) * ih
    p = [f'<svg viewBox="0 0 {w} {height}" class="chart">']
    for f in (0, .5, 1):
        val = mn + (mx - mn) * f
        yy = Y(val)
        p.append(f'<line x1="{pl}" y1="{yy:.0f}" x2="{w-pr}" y2="{yy:.0f}" stroke="{LINE}"/>')
        p.append(f'<text x="4" y="{yy+3:.0f}" class="ax">{_esc(fmt(val))}</text>')
    for s in series:
        d = " ".join(f'{"M" if i==0 else "L"} {X(i):.1f} {Y(v):.1f}' for i, v in enumerate(s["puntos"]))
        p.append(f'<path d="{d}" fill="none" stroke="{s["color"]}" stroke-width="2.5"/>')
        for i, v in enumerate(s["puntos"]):
            p.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.5" fill="{s["color"]}"><title>{_esc(labels[i])}: {_esc(fmt(v))}</title></circle>')
    for i, l in enumerate(labels):
        p.append(f'<text x="{X(i):.0f}" y="{height-10}" text-anchor="middle" class="ax">{_esc(l)}</text>')
    p.append("</svg>")
    leg = "".join(f'<span class="lg"><i style="background:{s["color"]}"></i>{_esc(s["nombre"])}</span>' for s in series)
    return "".join(p) + f'<div class="legend">{leg}</div>'


def _heatmap(celdas):
    if not celdas:
        return '<p class="muted">Sin datos de hora.</p>'
    horas = sorted({c["hora"] for c in celdas})
    cols = list(range(min(horas), max(horas) + 1))
    by = {(c["dow"], c["hora"]): c for c in celdas}
    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    cw, ch, lx, ty = 26, 24, 38, 18
    w, hh = lx + len(cols) * cw + 8, ty + 7 * ch + 8
    p = [f'<svg viewBox="0 0 {w} {hh}" class="chart">']
    for hi, hr in enumerate(cols):
        if hr % 2 == 0:
            p.append(f'<text x="{lx+hi*cw+cw/2:.0f}" y="{ty-5}" text-anchor="middle" class="ax">{hr}</text>')
    for r in range(7):
        p.append(f'<text x="{lx-5}" y="{ty+r*ch+ch/2+3:.0f}" text-anchor="end" class="ax">{dias[r]}</text>')
        for hi, hr in enumerate(cols):
            c = by.get((r, hr))
            x, y = lx + hi * cw, ty + r * ch
            fill = "#EEF0F3" if not c else _mix("#F3E7C9", "#0E9F6E", c["tasa"])
            t = f'{dias[r]} {hr}:00 — {c["tasa"]*100:.0f}% ({c["efectivos"]}/{c["toques"]})' if c else ""
            p.append(f'<rect x="{x}" y="{y}" width="{cw-2}" height="{ch-2}" rx="2" fill="{fill}"><title>{_esc(t)}</title></rect>')
    p.append("</svg>")
    return "".join(p)


def _mix(a, b, t):
    t = max(0.0, min(1.0, t))
    ah = [int(a[i:i+2], 16) for i in (1, 3, 5)]
    bh = [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(ah[i]+(bh[i]-ah[i])*t):02x}" for i in range(3))


def _table(headers, rows):
    h = "".join(f"<th>{_esc(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f'<td class="mono">{_esc(c)}</td>' for c in r) + "</tr>" for r in rows)
    return f'<table class="tbl"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>'


def _section(sid, eyebrow, titulo, cuerpo, lectura=None):
    lec = f'<p class="read">{cuerpo_read(lectura)}</p>' if lectura else ""
    return (f'<section id="{sid}"><div class="eyebrow">{_esc(eyebrow)}</div>'
            f'<h2>{_esc(titulo)}</h2>{lec}{cuerpo}</section>')


def cuerpo_read(s):
    return s  # permite HTML en la lectura


def build_report_html(ctx: dict[str, Any]) -> str:
    b = ctx["brand"]
    camp = ctx["campaign"]
    r = ctx["resumen"] or {}
    canal = ctx["canal"] or []
    e = ctx.get("estrategia") or {}
    ags = ctx.get("agentes") or []
    unidad = b.unidad_plural

    secciones = []
    nav = []

    def add(sid, label, eyebrow, titulo, cuerpo, lectura=None):
        nav.append((sid, label))
        secciones.append(_section(sid, eyebrow, titulo, cuerpo, lectura))

    # 01 · Resumen ejecutivo (KPIs + mirror header)
    kpis = [
        ("Recuperado", _money(r.get("recuperado")), _pct(r.get("pct_recuperado")) + " del saldo"),
        ("Saldo asignado", _money(r.get("saldo_asignado")), f'{_num(camp.get("deudas"))} deudas'),
        ("Deudas liquidadas", _num(r.get("deudas_liquidadas")), ""),
        ("% espontáneo", _pct(r.get("pct_espontaneo")), "sin contacto previo"),
        (f"% {unidad} sin contacto", _pct(r.get("pct_cartera_no_contactada")), ""),
        ("% fuera de ventana", _pct(r.get("pct_fuera_ventana")), "sesgo temporal"),
    ]
    kcards = "".join(f'<div class="kpi"><div class="kl">{_esc(l)}</div><div class="kv mono">{_esc(v)}</div><div class="ks">{_esc(s)}</div></div>' for l, v, s in kpis)
    er = e.get("esfuerzo_retorno") or []
    mirror = _mirror(er) if er else ""
    cuerpo01 = f'<div class="kpis">{kcards}</div>' + (f'<div class="eyebrow" style="margin-top:22px">La tesis en una imagen · reparto del esfuerzo vs. del dinero</div>{mirror}' if mirror else "")
    add("resumen", "Resumen", "01 · Panorama", "Qué se recuperó y con qué sesgos leerlo",
        cuerpo01,
        f'Se recuperó <b>{_money(r.get("recuperado"))}</b> ({_pct(r.get("pct_recuperado"))} del saldo). '
        f'<b>{_pct(r.get("pct_espontaneo"))}</b> llegó sin contacto efectivo previo y <b>{_pct(r.get("pct_fuera_ventana"))}</b> fuera de la ventana de gestión — ambos entran como espontáneo por construcción, no por mérito.')

    # 02 · Esfuerzo vs retorno
    if er:
        rows = [[x["temp"], _num(x["gestiones"]), _pct(x["pct_esfuerzo"]), _money(x["recuperado"]),
                 _pct(x["pct_recuperado"]), f'{x["pesos_por_gestion"]:.0f}'] for x in er]
        tbl = _table(["Tramo", "Gestiones", "% esfuerzo", "Recuperado", "% dinero", "$/gestión"], rows)
        ra = e.get("reasignacion")
        call = ""
        if ra:
            call = (f'<div class="callout"><b>Reasignación (supuestos pesimistas).</b> Mover el esfuerzo de '
                    f'<b>{_esc(ra["peor"])}</b> a <b>{_esc(ra["mejor"])}</b>: libera {_num(ra["gestiones_liberadas"])} gestiones '
                    f'({_pct(ra["pct_capacidad"])}), sacrifica {_money(ra["sacrificada"])}, suma {_money(ra["adicional"])} '
                    f'→ neto <b>{_money(ra["neto"])}</b> ({_pct(ra["neto_pct"])} del total).</div>')
        add("esfuerzo", "Esfuerzo", "02 · El titular", "¿Dónde está mal dirigido el esfuerzo?",
            _mirror(er) + tbl + call,
            "Si el reparto del esfuerzo y el del dinero están invertidos entre tramos, ahí está la fuga — por encima de cualquier optimización de canal.")

    # 03 · Truncamiento
    tr = e.get("truncamiento") or {}
    if tr.get("ingenua") and tr.get("corregida"):
        ing_bars = _bars([{"label": x["bucket"], "value": x["tasa"], "color": MUTED, "right": _pct(x["tasa"])} for x in tr["ingenua"]])
        cor_bars = _bars([{"label": x["bucket"], "value": x["hazard"], "color": RAMP[0], "right": _pct(x["hazard"], 2)} for x in tr["corregida"]])
        cuerpo = (f'<div class="two"><div><div class="tag bad">No usar para decidir · ingenua</div>{ing_bars}</div>'
                  f'<div><div class="tag good">Corregida · hazard diario</div>{cor_bars}</div></div>')
        add("truncamiento", "Truncamiento", "03 · Metodología", "La curva que engaña vs. la honesta",
            cuerpo,
            "La gestión se detiene cuando la dama paga, así que “más gestiones = menos pago” es un espejismo. El panel día-a-día lo corrige: cada dosis <b>sí</b> sube la probabilidad diaria de pago.")

    # 04 · Efecto por canal (hazard)
    hc = e.get("hazard_canal") or []
    if hc:
        bars = _bars([{"label": x["canal"], "value": max(0, x["lift"]), "color": CANAL_COL.get(x["canal"], SIGNAL),
                       "right": f'con {_pct(x["hazard_con"],2)} · sin {_pct(x["hazard_sin"],2)} · {x["lift"]*100:+.2f}pp'} for x in hc])
        add("canal", "Canal", "04 · Efecto aislado", "Qué canal mueve el pago, a igual día de riesgo",
            bars,
            "Probabilidad diaria de pago con vs. sin exposición al canal en los días previos. El lift es asociación controlada por tiempo en riesgo — no causa; sin grupo de control no se aísla el efecto.")

    # 05 · Modelos
    m = e.get("modelos") or {}
    if m.get("disponible"):
        parts = []
        if m.get("panel"):
            p = m["panel"]
            ob = _bars([{"label": o["var"], "value": min(o["or"], 10), "color": SIGNAL if o["or"] >= 1 else MUTED,
                         "right": f'×{o["or"]:.2f}'} for o in sorted(p["odds"], key=lambda x: -x["or"])], h=None)
            parts.append(f'<h3>Odds ratios (panel · válido para efectos) · AUC {p.get("auc",0):.3f}</h3>{ob}')
        if m.get("arbol"):
            rows = [[" · ".join(x["condiciones"]) or "(todas)", _num(x["n"]), _pct(x["tasa_real"])] for x in m["arbol"][:6]]
            parts.append("<h3>Reglas accionables (árbol · tasa real por hoja)</h3>" + _table(["Regla", "Damas", "Tasa real"], rows))
        if m.get("deciles"):
            db = _bars([{"label": f'Decil {d["decil"]}', "value": d["tasa_pago"], "color": RAMP[0],
                         "right": _pct(d["tasa_pago"])} for d in m["deciles"]])
            parts.append(f'<h3>Deciles de propensión (scoring por dama)</h3>{db}')
        add("modelos", "Modelos", "05 · Predicción", "Qué predice el pago y cómo priorizar",
            "".join(parts),
            "El efecto sale del panel (odds ratio ×N). El scoring por dama es para priorizar (marcado como sesgado).")

    # 06 · Canal (mezcla último toque)
    if canal:
        bars = _bars([{"label": ("Espontáneo" if c["canal"] == "Espontaneo" else c["canal"]),
                       "value": c["monto_ultimo_toque"], "color": CANAL_COL.get(c["canal"], SIGNAL),
                       "right": f'{_money(c["monto_ultimo_toque"])} · {_pct(c["pct"])}'} for c in canal])
        add("mezcla", "Mezcla", "06 · Atribución", "Recuperado por canal (último toque)",
            bars, "Modelo de último toque efectivo, ventana de 7 días. Correlación, no causa.")

    # 07 · Timing
    tm = e.get("timing") or {}
    if tm.get("disponible"):
        cap = ""
        if tm.get("mejor"):
            mj = tm["mejor"]
            cap = f'<p class="muted">Mejor franja: {_esc(mj["dow_lbl"])} {mj["hora"]}:00 — {_pct(mj["tasa"])} de contacto.</p>'
        add("timing", "Timing", "07 · Franja horaria", "Contactabilidad por día y hora",
            _heatmap(tm["celdas"]) + cap,
            "Verde = mayor tasa de contacto efectivo. Sale de la hora del crudo — el dato que suele faltar.")

    # 08 · Gestores
    if ags:
        top = sorted(ags, key=lambda a: -(a.get("recuperado_atribuido") or 0))[:10]
        rows = [[a.get("nombre") or "—", _num(a.get("gestiones")), _pct(a.get("tasa_contacto")),
                 _pct(a.get("pct_cumplimiento")), _money(a.get("recuperado_atribuido")),
                 (a.get("clasificacion") or "").replace("_", " ")] for a in top]
        add("gestores", "Gestores", "08 · Talento", "Desempeño por gestor",
            _table(["Gestor", "Gestiones", "Contacto", "Cumplim.", "Recuperado", "Clasificación"], rows),
            "Umbrales relativos a la mediana del equipo. Lenguaje de desarrollo, no de despido.")

    # 09 · ROI en pesos por canal
    roi = e.get("roi") or {}
    if roi.get("disponible") and roi.get("filas"):
        rows = [[f["canal"], _num(f["intentos"]), _money(f["costo"]), _money(f["recuperado"]),
                 _money(f["neto"]), (f'{f["roi"]:.1f}×' if f["roi"] else "—")] for f in roi["filas"]]
        rows.append(["Total", "", _money(roi["costo_total"]), _money(roi["recuperado_total"]),
                     _money(roi["neto_total"]), (f'{roi["roi_total"]:.1f}×' if roi.get("roi_total") else "—")])
        bars = _bars([{"label": f["canal"], "value": max(0.0, f["roi"] or 0),
                       "color": CANAL_COL.get(f["canal"], SIGNAL),
                       "right": f'{_money(f["recuperado"])} ÷ {_money(f["costo"])} = {f["roi"]:.1f}×' if f["roi"] else "sin costo"}
                      for f in roi["filas"]])
        add("roi", "ROI", "09 · Economía", "Retorno en pesos por canal",
            bars + _table(["Canal", "Intentos", "Costo", "Recuperado", "Neto", "ROI"], rows),
            "Recuperación atribuida (último toque) sobre el costo del canal, con costos unitarios de referencia. "
            "El marcador automático (C3) se carga a Llamada. Foto con supuestos explícitos, editable en la app.")

    # 10 · Segmentación (k-means)
    seg = e.get("segmentacion") or {}
    if seg.get("disponible") and seg.get("segmentos"):
        rows = [[s["etiqueta"], _num(s["damas"]), _pct(s["pct"]), _pct(s["tasa_pago"]),
                 f'{s["gestiones_prom"]:.1f}', _money(s["saldo_prom"]), _money(s["recuperado"]),
                 s["tramo_dominante"]] for s in seg["segmentos"]]
        bars = _bars([{"label": f'{s["etiqueta"]} · {s["tramo_dominante"]}', "value": s["tasa_pago"],
                       "color": RAMP[i % len(RAMP)], "right": f'{_pct(s["tasa_pago"])} · {_num(s["damas"])}'}
                      for i, s in enumerate(seg["segmentos"])])
        add("segmentos", "Segmentos", "10 · Segmentación", f"Perfiles de cartera (k-means, k={seg.get('k')})",
            bars + _table(["Segmento", unidad.capitalize(), "% cartera", "Tasa pago", "Gest. prom", "Saldo prom", "Recuperado", "Tramo dom."], rows),
            "Grupos por perfil de gestión y saldo (sin usar el pago para agrupar), descritos con su tasa real. "
            "Sirven para diseñar guiones y cadencias por segmento, no dama por dama.")

    # 11 · Correlación (palancas)
    cr = e.get("correlacion") or {}
    if cr.get("disponible") and cr.get("con_pago"):
        bars = _bars([{"label": c["var"], "value": abs(c["r"]), "color": SIGNAL if c["r"] >= 0 else MUTED,
                       "right": f'{c["r"]:+.2f}'} for c in cr["con_pago"][:6]])
        add("palancas", "Palancas", "11 · Correlación", "Qué se asocia al pago",
            bars,
            "Correlación de Pearson de cada palanca con el pago. Asociación, no causa — la causa la resuelve el panel hazard. "
            "Valores bajos son normales en cobranza: el pago depende de muchos factores.")

    navhtml = "".join(f'<a href="#{sid}"><span>{_esc(lbl)}</span></a>' for sid, lbl in nav)
    data_json = json.dumps(ctx.get("estrategia") or {}, ensure_ascii=False, default=str)
    titulo = f'{b.nombre} · Cobranza — {_esc(camp.get("anio_campania",""))}'
    sub = f'Snapshot {_esc(camp.get("fecha_snapshot") or "—")}'

    return _HTML.format(
        titulo=_esc(titulo), sub=sub, marca=_esc(b.nombre),
        nav=navhtml, secciones="".join(secciones), data=data_json,
        css=_CSS,
    )


_CSS = """
:root{--ink:#10192B;--ink2:#1B2942;--paper:#F6F7F9;--card:#FFF;--text:#14202F;--muted:#5C6B80;--line:#DFE5EC;--signal:#2B5FD9}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--text);font-family:'Source Sans 3',system-ui,sans-serif;line-height:1.5}
.mono{font-family:'IBM Plex Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums}
h1,h2,h3{font-family:'Bricolage Grotesque','Source Sans 3',sans-serif;color:var(--ink);letter-spacing:-.01em;line-height:1.15}
h1{font-size:2.2rem;margin:0} h2{font-size:1.5rem;margin:0 0 4px} h3{font-size:1.02rem;margin:22px 0 8px}
.wrap{display:grid;grid-template-columns:210px 1fr;max-width:1200px;margin:0 auto;gap:0}
header.mast{grid-column:1/-1;background:var(--ink);color:#fff;padding:34px 40px}
header.mast .eyebrow{color:#9fb0c9} header.mast h1{color:#fff} header.mast .sub{color:#c7d2e2;margin-top:6px;font-size:.95rem}
nav{position:sticky;top:0;align-self:start;height:100vh;overflow:auto;padding:24px 14px;border-right:1px solid var(--line)}
nav a{display:block;padding:7px 10px;border-radius:7px;color:var(--muted);text-decoration:none;font-size:.86rem}
nav a.active{background:var(--ink);color:#fff}
nav a:focus-visible{outline:2px solid var(--signal);outline-offset:2px}
main{padding:34px 40px}
section{padding:26px 0;border-bottom:1px solid var(--line)}
.eyebrow{font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:6px}
.read{color:var(--muted);max-width:60ch;margin:2px 0 16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:14px}
.kl{font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.kv{font-size:1.5rem;font-weight:600;color:var(--ink);margin:4px 0} .ks{font-size:.75rem;color:var(--muted)}
.bar{display:grid;grid-template-columns:130px 1fr auto;align-items:center;gap:12px;padding:5px 0}
.bl{font-size:.85rem;color:var(--muted)} .bt{height:20px;background:#ECEFF3;border-radius:5px;overflow:hidden}
.bf{display:block;height:100%;border-radius:5px} .br{font-size:.82rem;text-align:right;white-space:nowrap}
.mirror{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:8px}
.mh{display:grid;grid-template-columns:1fr 120px 1fr;gap:8px;font-size:.64rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px}
.mh span:first-child{text-align:right;padding-right:6px} .mh span:nth-child(2){text-align:center} .mh span:last-child{text-align:left;padding-left:6px}
.mr{display:grid;grid-template-columns:1fr 120px 1fr;align-items:center;gap:8px;padding:3px 0}
.ml{display:flex;justify-content:flex-end} .mb{display:block;height:16px} .ml .mb{border-radius:3px 0 0 3px} .mrr .mb{border-radius:0 3px 3px 0}
.mt{text-align:center;font-size:.82rem}
.tbl{width:100%;border-collapse:collapse;font-size:.86rem;margin-top:8px}
.tbl th{text-align:left;font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:8px 10px;border-bottom:1px solid var(--line)}
.tbl td{padding:8px 10px;border-bottom:1px solid var(--line)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.tag{display:inline-block;font-size:.7rem;font-weight:600;padding:3px 9px;border-radius:999px;margin-bottom:8px}
.tag.bad{background:#FDECEC;color:#B3312C} .tag.good{background:#E7F6EF;color:#0C7A57}
.callout{background:#FBF7EC;border:1px solid #EAD9AE;border-radius:10px;padding:14px 16px;margin-top:14px;font-size:.9rem}
.muted{color:var(--muted);font-size:.85rem}
svg.chart{width:100%;height:auto;max-width:640px;overflow:visible}
.ax{font-size:9px;fill:var(--muted)}
.legend{display:flex;gap:14px;margin-top:6px} .lg{display:inline-flex;align-items:center;gap:6px;font-size:.8rem;color:var(--muted)}
.lg i{width:9px;height:9px;border-radius:50%;display:inline-block}
footer{grid-column:1/-1;padding:26px 40px;color:var(--muted);font-size:.8rem;border-top:1px solid var(--line)}
@media (max-width:820px){.wrap{grid-template-columns:1fr}nav{display:none}.two{grid-template-columns:1fr}main{padding:22px}}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
@media print{nav{display:none}.wrap{grid-template-columns:1fr}section{break-inside:avoid}}
"""

_HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo}</title>
<link rel="stylesheet" media="print" onload="this.media='all'"
 href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=IBM+Plex+Mono:wght@400;500&family=Source+Sans+3:wght@400;600&display=swap">
<style>{css}</style></head><body>
<div class="wrap">
<header class="mast"><div class="eyebrow">{marca} · Inteligencia de Cobranza</div>
<h1>{titulo}</h1><div class="sub">{sub} · Informe de eficiencia de estrategias · corregido por sesgo de truncamiento</div></header>
<nav id="nav">{nav}</nav>
<main>{secciones}
<footer>Correlación controlada por tiempo en riesgo — no causalidad. Para prueba causal haría falta un grupo de control (champion/challenger). Faltan: hora de gestión a mayor resolución, costo unitario por canal, y ventana de gestión más larga frente al periodo de pagos. Generado por la plataforma de cobranza.</footer>
</main></div>
<script>
const DATA = {data};
const obs = new IntersectionObserver((es)=>{{es.forEach(e=>{{if(e.isIntersecting){{document.querySelectorAll('#nav a').forEach(a=>a.classList.remove('active'));const l=document.querySelector('#nav a[href="#'+e.target.id+'"]');if(l)l.classList.add('active');}}}});}},{{rootMargin:'-40% 0px -55% 0px'}});
document.querySelectorAll('main section').forEach(s=>obs.observe(s));
</script></body></html>"""
