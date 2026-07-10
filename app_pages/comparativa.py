"""Comparativa entre campañas (§8 pág. 9) — la vista que justifica el sistema."""
import streamlit as st

from cobranza import ui
from cobranza.charts import line_chart
from cobranza.format import money_k


def render():
    comp = ui.data().comparativa()
    camps = comp["campaigns"]
    if not camps:
        st.info("Sin campañas. Carga al menos una; con dos o más, esta vista muestra la tendencia sin recalcular a mano.")
        st.stop()

    ui.page_header("La vista que justifica el sistema", "Comparativa día a día / campaña a campaña",
                   "Cada punto es un snapshot (una carga diaria). Se ve cómo evoluciona la recuperación conforme la campaña madura, y campaña contra campaña. Ojo con la madurez — comparar una recién liberada contra una madura distorsiona la lectura.")

    if len(camps) < 2:
        ui.callout("info", "Solo hay un snapshot cargado",
                   "La tendencia aparece al cargar más días. El sistema ya guarda la serie; cada carga diaria suma un punto sin recalcular nada a mano.")

    # Etiqueta por día (snapshot); si hay varias campañas, antepone el código.
    multi = len({c["anio_campania"] for c in camps}) > 1
    labels = [
        (f'{c["anio_campania"]}·{(c.get("fecha_snapshot") or "")[5:]}' if multi else (c.get("fecha_snapshot") or c["anio_campania"]))
        for c in camps
    ]
    res_by = {r["campaign_id"]: r for r in comp["resumenes"]}
    recuperado = [res_by.get(c["id"], {}).get("recuperado", 0) for c in camps]
    espont = [res_by.get(c["id"], {}).get("pct_espontaneo", 0) * 100 for c in camps]
    cumpl = [comp["cumplimiento"].get(c["id"], 0) * 100 for c in camps]

    def canal_pct(canal):
        out = []
        for c in camps:
            row = next((x for x in comp["canales"] if x["campaign_id"] == c["id"] and x["canal"] == canal), None)
            out.append((row["pct"] if row else 0) * 100)
        return out

    c1, c2 = st.columns(2)
    with c1:
        ui.section("Recuperado por campaña")
        st.markdown(line_chart(labels, [{"nombre": "Recuperado", "color": "#12A99A", "puntos": recuperado}], fmt=money_k), unsafe_allow_html=True)
    with c2:
        ui.section("Cumplimiento vs. % espontáneo")
        st.markdown(line_chart(labels, [
            {"nombre": "Cumplimiento %", "color": "#B77E17", "puntos": cumpl},
            {"nombre": "% espontáneo", "color": "#8A94A3", "puntos": espont},
        ], fmt=lambda n: f"{n:.0f}%"), unsafe_allow_html=True)

    ui.section("Mezcla de canal (% recuperado, último toque)")
    st.markdown(line_chart(labels, [
        {"nombre": "Llamada", "color": "#B77E17", "puntos": canal_pct("Llamada")},
        {"nombre": "IVR", "color": "#D6486A", "puntos": canal_pct("IVR")},
        {"nombre": "SMS", "color": "#12A99A", "puntos": canal_pct("SMS")},
        {"nombre": "Espontáneo", "color": "#8A94A3", "puntos": canal_pct("Espontaneo")},
    ], fmt=lambda n: f"{n:.0f}%"), unsafe_allow_html=True)
