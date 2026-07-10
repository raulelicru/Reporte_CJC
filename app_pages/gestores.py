"""Gestores — clasificación por cuadrante + ficha individual (§8 pág. 6)."""
import html

import pandas as pd
import streamlit as st

from cobranza import ui
from cobranza.charts import line_chart, quadrant_chart
from cobranza.classify import ETIQUETA_CLASIFICACION
from cobranza.format import money, num, pct
from cobranza.theme import CHIP_CLASS


def render():
    actual, _ = ui.require_campaign()
    d = ui.data()
    agentes = d.agentes(actual["id"]) or []
    if not agentes:
        st.info("Sin gestores en esta campaña.")
        st.stop()
    historia = d.historia()

    ui.page_header("Desarrollo de talento", "Gestores — quién puede capacitar y quién necesita apoyo",
                   "Umbrales relativos a la mediana del equipo en esta campaña: alcance (contacto), calidad de negociación (cumplimiento de PDP) y rendimiento (recuperado por gestión). Lenguaje de coaching, nunca de despido.")

    # Selección de gestor
    nombres = {a.get("nombre") or a["agente_id"]: a["agente_id"] for a in agentes}
    sel_nombre = st.selectbox("Gestor en foco", list(nombres.keys()))
    sel = nombres[sel_nombre]

    ui.section("Cuadrante · contacto vs. cumplimiento (mediana del equipo)")
    st.markdown(quadrant_chart(agentes, sel), unsafe_allow_html=True)

    # Tabla de mando (ordenable nativamente)
    ui.section("Tabla de mando")
    df = pd.DataFrame([{
        "Gestor": a.get("nombre") or a["agente_id"][:8],
        "Gestiones": a["gestiones"],
        "Contacto %": round(a["tasa_contacto"] * 100, 1),
        "Cumplimiento %": round(a["pct_cumplimiento"] * 100, 1),
        "Recuperado": round(a["recuperado_atribuido"]),
        "Clasificación": a["clasificacion"].replace("_", " "),
    } for a in agentes])
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Ficha individual
    a = next(x for x in agentes if x["agente_id"] == sel)
    ui.section("Ficha del gestor")
    chip = CHIP_CLASS.get(a["clasificacion"], "")
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">'
        f'<h3 style="margin:0">{html.escape(sel_nombre)}</h3>'
        f'<span class="chip {chip}">{ETIQUETA_CLASIFICACION[a["clasificacion"]]}</span></div>',
        unsafe_allow_html=True)

    c = st.columns(4)
    for col, (label, val) in zip(c, [
        ("Gestiones", num(a["gestiones"])), ("Tasa de contacto", pct(a["tasa_contacto"])),
        ("Cumplimiento PDP", pct(a["pct_cumplimiento"])), ("Recuperado", money(a["recuperado_atribuido"])),
    ]):
        with col:
            st.markdown(f'<div class="panel"><div class="eyebrow">{label}</div>'
                        f'<div class="num" style="font-size:1.1rem;font-weight:600">{val}</div></div>', unsafe_allow_html=True)

    if a["clasificacion"] == "PLAN_MEJORA":
        mentor = a.get("mentor_nombre")
        if mentor:
            ui.callout("warn", "Emparejamiento sugerido",
                       f"Acompañar con <b>{html.escape(mentor)}</b> (mentor con mayor cumplimiento y capacidad). Es desarrollo de talento: necesita apoyo en cierre, no es un mal gestor.")
        else:
            ui.callout("warn", "Emparejamiento sugerido", "Aún no hay un mentor identificado en el equipo para esta campaña.")

    ui.section("Evolución campaña a campaña")
    h = next((v for v in historia.values() if v["display"] == sel_nombre), None)
    if h and len(h["puntos"]) > 1:
        labels = [p["anio"] for p in h["puntos"]]
        series = [
            {"nombre": "Contacto %", "color": "#B77E17", "puntos": [p["contacto"] * 100 for p in h["puntos"]]},
            {"nombre": "Cumplimiento %", "color": "#12A99A", "puntos": [p["cumplimiento"] * 100 for p in h["puntos"]]},
        ]
        st.markdown(line_chart(labels, series, fmt=lambda n: f"{n:.0f}%"), unsafe_allow_html=True)
    else:
        st.caption("Solo hay una campaña para este gestor. Al cargar más campañas se verá aquí si mejoró su contacto y su cumplimiento — ese es el punto de guardar la historia.")
