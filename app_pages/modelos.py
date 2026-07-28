"""Modelos predictivos + roll-rate (Fase B)."""
import pandas as pd
import streamlit as st

from cobranza import ui
from cobranza.analytics import roll_rate
from cobranza.charts import bar_list
from cobranza.format import num, pct


def render():
    actual, camps = ui.require_campaign()
    e = ui.data().estrategia(actual["id"])
    m = (e or {}).get("modelos") if e else None

    ui.page_header("Modelos predictivos", "Qué predice el pago, y cómo priorizar",
                   "El efecto sale del panel día-a-día (válido). El scoring por dama es para priorizar, marcado como tal (sesgado por truncamiento).")

    if not m or not m.get("disponible"):
        st.info("Modelos no disponibles (datos insuficientes o campaña sin recalcular). Vuelve a confirmar la campaña.")
    else:
        _panel(m)
        _deciles(m)
        _arbol(m)

    _rollrate(actual, camps)


def _panel(m):
    p = m.get("panel")
    if not p:
        return
    ui.section("Efecto por variable (panel día-a-día)", "Válido para efectos",
               "Odds ratio: cuánto multiplica las odds de pagar ese día. >1 sube, <1 baja. Controlado por tiempo en riesgo.")
    if p.get("auc"):
        st.caption(f"AUC del modelo de panel: {p['auc']:.3f} · {num(p['n'])} filas dama-día.")
    items = []
    for o in sorted(p["odds"], key=lambda x: -x["or"]):
        val = o["or"]
        items.append({"label": o["var"], "value": min(val, 10),
                      "fill": "fill-llamada" if val >= 1 else "fill-espontaneo",
                      "right": f'×{val:.2f}'})
    st.markdown(bar_list(items, max_value=10), unsafe_allow_html=True)
    st.caption("Referencia: ×1.00 = sin efecto. (Escala recortada a ×10 para lectura.)")


def _deciles(m):
    dec = m.get("deciles")
    if not dec:
        return
    auc = m.get("dama_auc")
    ui.section("Priorización por decil (scoring por dama)", "Para priorizar · sesgado",
               "Ordena las damas por probabilidad de pago. El decil 1 son las más propensas — dónde concentrar el mejor esfuerzo.")
    if auc:
        st.caption(f"AUC del scoring por dama: {auc:.3f}.")
    df = pd.DataFrame([{"Decil": d["decil"], "Damas": d["damas"],
                        "Tasa de pago": round(d["tasa_pago"] * 100, 1),
                        "Gestiones prom.": round(d["gestiones_prom"], 2)} for d in dec])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown(bar_list([{"label": f'Decil {d["decil"]}', "value": d["tasa_pago"], "fill": "fill-sms",
                           "right": pct(d["tasa_pago"])} for d in dec],
                         max_value=max([d["tasa_pago"] for d in dec] + [0.01])), unsafe_allow_html=True)


def _arbol(m):
    reglas = m.get("arbol")
    if not reglas:
        return
    ui.section("Reglas accionables (árbol, tasas reales por hoja)", "Segmentación por reglas",
               "Cada hoja del árbol es una regla. La tasa es la REAL del segmento (no la balanceada del modelo).")
    df = pd.DataFrame([{"Regla": " · ".join(r["condiciones"]) or "(todas)",
                        "Damas": r["n"], "Tasa real de pago": round(r["tasa_real"] * 100, 1)}
                       for r in reglas])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _rollrate(actual, camps):
    ui.section("Roll-rate: migración de temporalidad", "Dinámica de cartera",
               "Cómo ruedan las damas entre tramos de un snapshot al siguiente. Necesita ≥2 snapshots.")
    d = ui.data()
    e_cur = d.estrategia(actual["id"])
    # Snapshot anterior de la misma campaña (o campaña previa).
    ordenadas = sorted(camps, key=lambda c: (c["anio_campania"], c.get("fecha_snapshot") or ""))
    idx = next((i for i, c in enumerate(ordenadas) if c["id"] == actual["id"]), 0)
    if idx <= 0:
        st.info("Solo hay un snapshot. Carga otro día u otra campaña para ver la migración.")
        return
    prev = ordenadas[idx - 1]
    e_prev = d.estrategia(prev["id"])
    tp = (e_prev or {}).get("temp_por_dama") or {}
    tc = (e_cur or {}).get("temp_por_dama") or {}
    rr = roll_rate(tp, tc, ui.brand_of(actual))
    if not rr.get("disponible"):
        st.info("No hay temporalidad comparable entre los dos snapshots todavía.")
        return
    st.caption(f'De {prev.get("fecha_snapshot")} a {actual.get("fecha_snapshot")} · {num(rr["damas"])} damas comunes.')
    rows = []
    for f in rr["filas"]:
        dest = ", ".join(f'{x["hacia"]} {pct(x["pct"],0)}' for x in f["destinos"])
        rows.append({"Desde": f["desde"], "Damas": f["total"], "Hacia": dest})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
