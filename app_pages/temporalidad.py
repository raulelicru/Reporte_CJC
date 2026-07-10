"""Temporalidad (§8 pág. 7)."""
import pandas as pd
import streamlit as st

from cobranza import ui
from cobranza.format import money_k, num, pct


def render():
    actual, _ = ui.require_campaign()
    tramos = ui.data().temporalidad(actual["id"]) or []
    if not tramos:
        st.info("Sin tramos de morosidad.")
        st.stop()

    ui.page_header("Tramos de morosidad", "Saldo vs. recuperado por temporalidad",
                   "El tramo (Mora 1–3, MNI, IM, Inactiva) se mapea por consultora desde gestiones/IVR — no viene en la cartera.")

    sorted_t = sorted(tramos, key=lambda t: t["saldo"], reverse=True)
    bolsas = [t for t in sorted_t if t["tasa"] < 0.2]
    if bolsas:
        b = max(bolsas, key=lambda t: t["saldo"])
        ui.callout("crit", "Mayor bolsa con baja recuperación",
                   f"<b>{b['temp']}</b> concentra {money_k(b['saldo'])} de saldo con solo {pct(b['tasa'])} recuperado. Es la prioridad de intervención.")

    df = pd.DataFrame([{
        "Tramo": t["temp"], "Deudas": t["deudas"], "Saldo": round(t["saldo"]),
        "Recuperado": round(t["recuperado"]), "Tasa %": round(t["tasa"] * 100, 1),
    } for t in sorted_t])
    st.dataframe(df, use_container_width=True, hide_index=True)
