"""ARABELA · Plataforma de Inteligencia de Cobranza — entrada Streamlit.

Auth-gated con st.navigation: sin sesión solo se ve el login; con sesión, la
navegación completa (§8) con selector de campaña siempre visible.
"""
import streamlit as st

from cobranza import theme, ui
from cobranza.format import money_k, num
from app_pages import (
    canales,
    carga,
    comparativa,
    gestionado,
    gestores,
    login,
    metodologia,
    promesas,
    resumen,
    secuencias,
    temporalidad,
    tendencia,
)

st.set_page_config(page_title="Arabela · Cobranza", page_icon="◆", layout="wide")
theme.inject()

# Estado inicial
for k, v in {"authed": False, "demo": False, "cid": None}.items():
    st.session_state.setdefault(k, v)

# ── Gate de autenticación ──
if not st.session_state.get("authed"):
    login.render()
    st.stop()

# ── Sidebar: identidad + selector de campaña + logout ──
with st.sidebar:
    st.markdown('<div style="padding:4px 0 10px"><div style="font-family:Fraunces,serif;font-size:1.15rem;font-weight:600">Arabela</div>'
                '<div class="eyebrow">Inteligencia de Cobranza</div></div>', unsafe_allow_html=True)

    actual, camps = ui.selected_campaign()
    if camps:
        labels = {f'{c["anio_campania"]} · {c["nombre"]}': c["id"] for c in camps}
        cur_label = next((k for k, v in labels.items() if v == st.session_state["cid"]), list(labels.keys())[0])
        chosen = st.selectbox("Campaña", list(labels.keys()), index=list(labels.keys()).index(cur_label))
        st.session_state["cid"] = labels[chosen]
        ui.campaign_badge(actual)
        st.caption(f'Saldo {money_k(actual.get("saldo_asignado"))} · {num(actual.get("deudas"))} deudas · {num(actual.get("consultoras"))} consultoras')
    else:
        st.caption("No hay campañas cargadas. Usa Carga de datos o el modo demo.")

    st.divider()
    prof = st.session_state.get("profile") or {}
    st.caption(f'Rol: {prof.get("rol", "—")}{" · demo" if st.session_state.get("demo") else ""}')
    if st.button("Cerrar sesión", use_container_width=True):
        for k in ["authed", "demo", "client", "store", "user_id", "profile", "cid"]:
            st.session_state.pop(k, None)
        st.rerun()

# ── Navegación (§8) ──
def _p(fn, title, icon, path, default=False):
    return st.Page(fn, title=title, icon=icon, url_path=path, default=default)

paginas = [
    _p(resumen.render, "Resumen ejecutivo", ":material/dashboard:", "resumen", default=True),
    _p(canales.render, "Recuperación por canal", ":material/bar_chart:", "canales"),
    _p(promesas.render, "Promesas de pago", ":material/handshake:", "promesas"),
    _p(secuencias.render, "Secuencias", ":material/timeline:", "secuencias"),
    _p(gestionado.render, "Gestionado vs. espontáneo", ":material/compare_arrows:", "gestionado"),
    _p(gestores.render, "Gestores", ":material/groups:", "gestores"),
    _p(temporalidad.render, "Temporalidad", ":material/schedule:", "temporalidad"),
    _p(tendencia.render, "Tendencia diaria", ":material/show_chart:", "tendencia"),
    _p(comparativa.render, "Comparativa entre campañas", ":material/stacked_line_chart:", "comparativa"),
]
if ui.is_admin():
    paginas.append(_p(carga.render, "Carga de datos", ":material/upload_file:", "carga"))
paginas.append(_p(metodologia.render, "Metodología", ":material/menu_book:", "metodologia"))

st.navigation(paginas).run()
