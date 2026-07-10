"""Secuencias (§8 pág. 4)."""
import streamlit as st

from cobranza import ui
from cobranza.charts import bar_list
from cobranza.format import money_k, num


def render():
    actual, _ = ui.require_campaign()
    seqs = ui.data().secuencias(actual["id"]) or []
    if not seqs:
        st.info("Sin secuencias.")
        st.stop()

    ui.page_header("Antes del pago", "Top cadenas de canal previas al pago",
                   "Cadenas de contactos efectivos en los 14 días previos al pago, colapsando repeticiones consecutivas del mismo canal.")
    items = [{"label": s["cadena"], "value": s["pagos"], "fill": "fill-llamada",
              "right": f"{num(s['pagos'])} pagos · {money_k(s['recuperado'])}"}
             for s in sorted(seqs, key=lambda x: x["pagos"], reverse=True)]
    st.markdown(bar_list(items), unsafe_allow_html=True)

    ui.callout("info", "No hay orquestación mágica",
               "Los toques sueltos ≈ las cadenas por ticket. La recuperación viene sobre todo de contactos individuales, no de secuencias multicanal orquestadas. Leerlas como “embudos” sobreinterpreta el dato.")
