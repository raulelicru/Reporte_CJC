"""Cálculo de métricas derivadas (§5) a partir del dataset normalizado.

Usa el motor de atribución y la clasificación de gestores. No se escribe una
sola cifra que no salga de aquí (§11).
"""
from __future__ import annotations

from typing import Any

from .attribution import (
    Payment,
    Touch,
    attribute_all,
    dif_dias,
    eficiencia_por_toque,
    influence_model,
    resumen_primario,
    sesgo_temporal,
)
from .classify import GestorInput, clasificar_equipo
from .ingest import IngestResult
from .predicates import gestion_efectiva


def compute_metrics(ing: IngestResult) -> dict[str, Any]:
    corte = ing.profile.get("fecha_corte_datos")

    payments = [
        Payment(p["dama_deuda"], p["num_dama"], p["fecha_pago"], p["recuperado"])
        for p in ing.pagos
        if p["fecha_pago"] and p["recuperado"] > 0
    ]
    touches = [Touch(t["num_dama"], t["canal"], t["dia"], t["efectivo"], t["meta"]) for t in ing.toques]

    atribs = attribute_all(payments, touches, corte)
    primario = resumen_primario(atribs)
    influencia = influence_model(payments, touches)["canales"]
    ef = eficiencia_por_toque(atribs, touches)
    sesgo = sesgo_temporal(payments, corte)

    total = sum(p.recuperado for p in payments)
    infl_by = {i["canal"]: i for i in influencia}
    primario_by = {p["canal"]: p for p in primario}

    canal = []
    for c in ("Llamada", "IVR", "SMS", "Espontaneo"):
        p = primario_by.get(c)
        inf = infl_by.get(c)
        canal.append({
            "canal": c,
            "monto_ultimo_toque": p["monto"] if p else 0.0,
            "pagos": p["pagos"] if p else 0,
            "consultoras": p["consultoras"] if p else 0,
            "pct": p["pct"] if p else 0.0,
            "eficiencia_por_toque": 0.0 if c == "Espontaneo" else ef[c],
            "influencia_monto": inf["monto"] if inf else 0.0,
            "influencia_pct": inf["pct"] if inf else 0.0,
        })

    agentes = _compute_agentes(ing, atribs)
    temporalidad = _compute_temporalidad(ing)
    diaria = _compute_diaria(ing, corte)
    secuencias = _compute_secuencias(payments, touches)

    espont = primario_by.get("Espontaneo")
    deudas_liquidadas = sum(1 for p in ing.pagos if p["saldo_remanente"] <= 0)
    damas_contactadas = {t["num_dama"] for t in ing.toques if t["efectivo"]}
    damas_cartera = {c["num_dama"] for c in ing.cartera}
    no_contactadas = sum(1 for d in damas_cartera if d not in damas_contactadas)
    saldo_asignado = ing.header["saldo_asignado"]

    resumen = {
        "recuperado": total,
        "saldo_asignado": saldo_asignado,
        "pct_recuperado": total / saldo_asignado if saldo_asignado > 0 else 0.0,
        "deudas_liquidadas": deudas_liquidadas,
        "saldo_pendiente": saldo_asignado - total,
        "pct_pagos_sin_contacto": (espont["monto"] / total) if (espont and total > 0) else 0.0,
        "pct_espontaneo": espont["pct"] if espont else 0.0,
        "pct_fuera_ventana": sesgo["pct_fuera_de_ventana"],
        "pct_cartera_no_contactada": (no_contactadas / len(damas_cartera)) if damas_cartera else 0.0,
    }

    return {"canal": canal, "agentes": agentes, "temporalidad": temporalidad,
            "diaria": diaria, "secuencias": secuencias, "resumen": resumen}


def _compute_agentes(ing: IngestResult, atribs) -> list[dict]:
    rec_by_agente: dict[str, float] = {}
    for a in atribs:
        if a.canal != "Llamada" or not a.touch:
            continue
        agente = a.touch.meta.get("agente")
        if not agente:
            continue
        rec_by_agente[agente] = rec_by_agente.get(agente, 0.0) + a.payment.recuperado

    pago_by_dama: dict[int, str] = {}
    for p in ing.pagos:
        if p["fecha_pago"] and p["recuperado"] > 0:
            pago_by_dama[p["num_dama"]] = p["fecha_pago"]

    acc: dict[str, dict] = {}
    display: dict[str, str] = {}
    for g in ing.gestiones:
        agente = g["agente_norm"]
        if not agente:
            continue
        display[agente] = g.get("agente_display") or agente
        cur = acc.setdefault(agente, {"gestiones": 0, "contactos": 0, "pdp": 0, "pdp_cumplidas": 0})
        cur["gestiones"] += 1
        if gestion_efectiva(g["tipo_gestion"]):
            cur["contactos"] += 1
        if g["promesa_fecha"]:
            cur["pdp"] += 1
            pago = pago_by_dama.get(g["num_dama"])
            if pago and -365 <= dif_dias(pago, g["promesa_fecha"]) <= 3:
                cur["pdp_cumplidas"] += 1

    inputs = [
        GestorInput(agente_id=a, nombre=display.get(a, a), gestiones=v["gestiones"],
                    contactos_efectivos=v["contactos"], pdp=v["pdp"], pdp_cumplidas=v["pdp_cumplidas"],
                    recuperado_atribuido=rec_by_agente.get(a, 0.0))
        for a, v in acc.items()
    ]
    clasificados = clasificar_equipo(inputs)
    return [vars(g) for g in clasificados]


def _compute_temporalidad(ing: IngestResult) -> list[dict]:
    temp_by_dama: dict[int, str] = {}
    for g in ing.gestiones:
        if g["temp"]:
            temp_by_dama[g["num_dama"]] = g["temp"]
    rec_by_dama: dict[int, float] = {}
    for p in ing.pagos:
        rec_by_dama[p["num_dama"]] = rec_by_dama.get(p["num_dama"], 0.0) + p["recuperado"]

    acc: dict[str, dict] = {}
    for c in ing.cartera:
        temp = temp_by_dama.get(c["num_dama"], "Sin tramo")
        cur = acc.setdefault(temp, {"saldo": 0.0, "recuperado": 0.0, "deudas": 0})
        cur["saldo"] += c["saldo_cobro"]
        cur["recuperado"] += rec_by_dama.get(c["num_dama"], 0.0)
        cur["deudas"] += 1

    out = [{"temp": t, "saldo": v["saldo"], "recuperado": v["recuperado"],
            "tasa": (v["recuperado"] / v["saldo"]) if v["saldo"] > 0 else 0.0, "deudas": v["deudas"]}
           for t, v in acc.items()]
    return sorted(out, key=lambda x: x["saldo"], reverse=True)


def _compute_diaria(ing: IngestResult, corte) -> list[dict]:
    acc: dict[str, dict] = {}
    for p in ing.pagos:
        if not p["fecha_pago"]:
            continue
        cur = acc.setdefault(p["fecha_pago"], {"recuperado": 0.0, "pagos": 0, "sms": 0})
        cur["recuperado"] += p["recuperado"]
        cur["pagos"] += 1
    for t in ing.toques:
        if t["canal"] != "SMS":
            continue
        cur = acc.setdefault(t["dia"], {"recuperado": 0.0, "pagos": 0, "sms": 0})
        cur["sms"] += 1

    sms_vals = [v["sms"] for v in acc.values() if v["sms"] > 0]
    media = (sum(sms_vals) / len(sms_vals)) if sms_vals else 0.0
    out = [{"fecha": f, "recuperado": v["recuperado"], "pagos": v["pagos"], "sms_enviados": v["sms"],
            "es_blast": media > 0 and v["sms"] > media * 2.5,
            "fuera_ventana": corte is not None and f > corte}
           for f, v in acc.items()]
    return sorted(out, key=lambda x: x["fecha"])


def _compute_secuencias(payments, touches) -> list[dict]:
    ef_por_dama: dict[int, list] = {}
    for t in touches:
        if not t.efectivo:
            continue
        ef_por_dama.setdefault(t.num_dama, []).append(t)

    acc: dict[str, dict] = {}
    for p in payments:
        arr = sorted(
            (t for t in ef_por_dama.get(p.num_dama, []) if 0 <= dif_dias(p.fecha_pago, t.dia) <= 14),
            key=lambda t: t.dia,
        )
        if not arr:
            continue
        cadena = []
        for t in arr:
            if not cadena or cadena[-1] != t.canal:
                cadena.append(t.canal)
        key = "→".join(cadena)
        cur = acc.setdefault(key, {"pagos": 0, "recuperado": 0.0})
        cur["pagos"] += 1
        cur["recuperado"] += p.recuperado

    out = [{"cadena": k, "pagos": v["pagos"], "recuperado": v["recuperado"]} for k, v in acc.items()]
    return sorted(out, key=lambda x: x["pagos"], reverse=True)[:8]
