"""Gestionado vs. espontáneo (§8 pág. 5)."""
import streamlit as st

from cobranza import ui
from cobranza.charts import bar_list
from cobranza.format import money, money_k, pct


def render():
    actual, _ = ui.require_campaign()
    d = ui.data()
    canales = d.canal(actual["id"]) or []
    r = d.resumen(actual["id"])
    if not canales or not r:
        st.info("Sin métricas.")
        st.stop()

    gestionado = sum(c["monto_ultimo_toque"] for c in canales if c["canal"] != "Espontaneo")
    espontaneo = next((c["monto_ultimo_toque"] for c in canales if c["canal"] == "Espontaneo"), 0.0)
    total = gestionado + espontaneo

    ui.page_header("El número incómodo", "Gestionado vs. espontáneo",
                   "Recuperado atribuible a un contacto efectivo previo (ventana 7 días) frente al que llegó sin toque previo.")
    st.markdown(bar_list([
        {"label": "Gestionado", "value": gestionado, "fill": "fill-llamada",
         "right": f"{money_k(gestionado)} · {pct(gestionado / total if total else 0)}"},
        {"label": "Espontáneo", "value": espontaneo, "fill": "fill-espontaneo",
         "right": f"{money_k(espontaneo)} · {pct(espontaneo / total if total else 0)}"},
    ]), unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        ui.kpi("Recuperado gestionado", money(gestionado))
    with c2:
        ui.kpi("Recuperado espontáneo", money(espontaneo))

    ui.callout("warn", "Sesgo temporal declarado en pantalla",
               f"{pct(r['pct_fuera_ventana'])} del recuperado ocurrió después del corte de datos de canal ({actual.get('fecha_corte_datos') or 's/f'}). Ese tramo no puede recibir atribución y engrosa el “espontáneo” por construcción, no porque la gestión haya fallado. Sin grupo de control no se aísla el efecto del recordatorio.")
