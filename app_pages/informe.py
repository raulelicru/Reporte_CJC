"""Informe — el reporte HTML autocontenido, embebido dentro de la app."""
import streamlit as st
import streamlit.components.v1 as components

from cobranza import ui
from cobranza.report import build_report_html


def render():
    actual, _ = ui.require_campaign()
    d = ui.data()
    e = d.estrategia(actual["id"])
    if not e or not e.get("disponible"):
        ui.page_header("Informe ejecutivo", "El informe se genera desde la analítica de estrategia")
        st.info("Aún no hay analítica para esta campaña. Vuelve a confirmarla en Carga de datos.")
        st.stop()

    ctx = {
        "brand": ui.brand_of(actual), "campaign": actual,
        "resumen": d.resumen(actual["id"]), "canal": d.canal(actual["id"]),
        "agentes": d.agentes(actual["id"]), "estrategia": e,
    }
    try:
        html = build_report_html(ctx)
    except Exception as ex:
        ui.page_header("Informe ejecutivo", "Error al generar el informe")
        st.error(f"No se pudo generar el informe: {ex}")
        st.stop()

    ui.page_header("Informe ejecutivo", "El reporte completo, embebido y descargable",
                   "Mismo informe autocontenido que puedes descargar como un solo .html para compartir o proyectar en comité.")
    nombre = f'informe_{actual.get("anio_campania","")}_{actual.get("fecha_snapshot","")}.html'
    st.download_button("⬇ Descargar informe HTML", data=html, file_name=nombre,
                       mime="text/html", type="primary")
    st.caption("El informe tiene su propia navegación (barra lateral interna). Desplázate dentro del marco.")
    components.html(html, height=1600, scrolling=True)
