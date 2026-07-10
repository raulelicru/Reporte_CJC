"""Tendencia diaria (§8 pág. 8)."""
import streamlit as st

from cobranza import ui
from cobranza.charts import column_chart
from cobranza.format import money_k, num


def render():
    actual, _ = ui.require_campaign()
    dias = ui.data().diaria(actual["id"]) or []
    if not dias:
        st.info("Sin serie diaria.")
        st.stop()

    ui.page_header("Día a día", "Tendencia diaria de recuperación")
    ui.correlacion_nota()
    st.caption("Barras por día. El tramo en gris es posterior al corte de datos de canal (fuera de ventana): no puede recibir atribución.")

    recuperado = [{"label": d["fecha"], "value": d["recuperado"], "muted": d.get("fuera_ventana")} for d in dias]
    st.markdown(column_chart(recuperado, fmt=money_k), unsafe_allow_html=True)
    fuera = sum(1 for d in dias if d.get("fuera_ventana"))
    if fuera:
        st.caption(f"Gris = {num(fuera)} días fuera de ventana.")

    ui.section("Blasts de SMS por día", "Envíos")
    sms = [{"label": d["fecha"], "value": d["sms_enviados"], "highlight": d.get("es_blast")} for d in dias]
    st.markdown(column_chart(sms, fmt=num), unsafe_allow_html=True)
    blasts = sum(1 for d in dias if d.get("es_blast"))
    st.caption(f"En teal, {num(blasts)} días marcados como blast (pico > 2.5× la media). Que un pico de SMS coincida con recuperación es correlación, no causa.")
