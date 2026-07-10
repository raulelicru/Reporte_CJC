"""Promesas de pago (§8 pág. 3)."""
import pandas as pd
import streamlit as st

from cobranza import ui
from cobranza.format import money, num, pct


def render():
    actual, _ = ui.require_campaign()
    agentes = ui.data().agentes(actual["id"]) or []
    if not agentes:
        st.info("Sin datos de promesas.")
        st.stop()

    pdp = sum(a["pdp"] for a in agentes)
    cumplidas = sum(a["pdp_cumplidas"] for a in agentes)
    recuperado = sum(a["recuperado_atribuido"] for a in agentes)
    tasa = cumplidas / pdp if pdp else 0.0

    ui.page_header("Compromisos de pago", "Promesas de pago (PDP)",
                   "Cumplida = pago dentro de la fecha prometida + 3 días. El monto prometido es aspiracional, no cobrado.")
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.kpi("Promesas registradas", num(pdp))
    with c2:
        ui.kpi("Promesas cumplidas", num(cumplidas))
    with c3:
        ui.kpi("Tasa de cumplimiento", pct(tasa))

    ui.section("Prometido vs. recuperado real", "Brecha")
    ui.callout("warn", "El prometido es aspiracional",
               f"El archivo de gestiones no trae monto prometido por promesa (campo ausente, §3), así que la brecha se lee en tasa de cumplimiento, no en pesos. Hook dejado. Recuperado atribuido a Llamada: <b>{money(recuperado)}</b>.")

    ui.section("Cumplimiento de promesas por gestor", "Detalle")
    rows = sorted(agentes, key=lambda a: a["pct_cumplimiento"], reverse=True)
    df = pd.DataFrame([{
        "Gestor": a.get("nombre") or a["agente_id"][:8],
        "PDP": a["pdp"], "Cumplidas": a["pdp_cumplidas"],
        "% cumplimiento": round(a["pct_cumplimiento"] * 100, 1),
    } for a in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Cumplimiento por debajo de ~32% = compromisos poco firmes ⇒ coaching de cierre, nunca despido automático.")
