"""Recuperación por canal (§8 pág. 2)."""
import streamlit as st

from cobranza import ui
from cobranza.charts import bar_list, channel_tag, fill_class
from cobranza.format import money, money_k, num, pct


def render():
    actual, _ = ui.require_campaign()
    canales = ui.data().canal(actual["id"]) or []
    if not canales:
        st.info("Sin métricas de canal.")
        st.stop()

    ui.page_header("Modelo primario · último toque efectivo", "Recuperación por canal")
    ui.correlacion_nota()
    st.caption("Cada pago se asigna al último canal con contacto efectivo en la ventana de 7 días. Empate el mismo día: Llamada > IVR > SMS.")

    primario = sorted(
        [{"label": c["canal"], "value": c["monto_ultimo_toque"], "fill": fill_class(c["canal"]),
          "right": f"{money_k(c['monto_ultimo_toque'])} · {pct(c['pct'])}"} for c in canales],
        key=lambda x: x["value"], reverse=True)
    st.markdown(bar_list(primario), unsafe_allow_html=True)

    reales = [c for c in canales if c["canal"] != "Espontaneo"]

    ui.section("Eficiencia por toque", "Apoyo")
    cols = st.columns(3)
    for i, c in enumerate(reales):
        with cols[i % 3]:
            st.markdown(
                f'<div class="panel">{channel_tag(c["canal"])}'
                f'<div class="num" style="font-size:1.25rem;font-weight:600;margin-top:4px">{money(c["eficiencia_por_toque"])}</div>'
                f'<div style="color:#5A6472;font-size:.75rem">recuperado atribuido ÷ toque efectivo</div></div>',
                unsafe_allow_html=True)

    suma = sum(c["influencia_pct"] for c in reales)
    ui.section("Influencia por canal", "Modelo secundario · any-touch",
               "% del monto de consultoras que recibieron ≥1 contacto efectivo de cada canal.")
    ui.callout("warn", f"La suma da {pct(suma)} — y está bien",
               "La influencia se cuenta por canal sin ventana, así que una misma consultora suma en varios canales. Por eso pasa de 100%. Es alcance, no atribución exclusiva.")
    infl = [{"label": c["canal"], "value": c["influencia_pct"], "fill": fill_class(c["canal"]),
             "right": f"{pct(c['influencia_pct'])} · {num(c.get('consultoras', 0))} consultoras"} for c in reales]
    st.markdown(bar_list(infl, max_value=max([c["influencia_pct"] for c in reales] + [0.01])), unsafe_allow_html=True)
