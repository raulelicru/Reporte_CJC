"""Pantalla de login (§7). Supabase Auth (email+contraseña) o modo demo."""
import streamlit as st

from cobranza import db
from cobranza.demo import build_demo


def render():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('<div style="text-align:center;margin-top:8vh">'
                    '<div style="font-family:Fraunces,serif;font-size:1.8rem;font-weight:600">Arabela</div>'
                    '<div class="eyebrow">Inteligencia de Cobranza</div></div>', unsafe_allow_html=True)

        with st.container(border=True):
            configured = db.is_configured()
            if not configured:
                st.info("Supabase no está configurado. Puedes explorar toda la app en **modo demo** con datos sintéticos.")

            email = st.text_input("Correo", placeholder="tu@correo.com", disabled=not configured)
            password = st.text_input("Contraseña", type="password", disabled=not configured)

            if st.button("Entrar", type="primary", use_container_width=True, disabled=not configured):
                _do_login(email, password)

            if st.button("Entrar en modo demo (datos sintéticos)", use_container_width=True):
                st.session_state["demo"] = True
                st.session_state["authed"] = True
                st.session_state["store"] = build_demo()
                st.session_state["profile"] = {"rol": "admin", "nombre": "Demo", "org_id": db.DEFAULT_ORG}
                st.rerun()

        st.caption("Acceso restringido. Sin sesión no se entra a ninguna vista.")


def _do_login(email, password):
    if not email or not password:
        st.error("Ingresa correo y contraseña.")
        return
    try:
        client = db.anon_client()
        res = db.sign_in(client, email, password)
        user = res.user
        if not user:
            st.error("Credenciales inválidas.")
            return
        st.session_state["authed"] = True
        st.session_state["demo"] = False
        st.session_state["client"] = client
        st.session_state["user_id"] = user.id
        st.session_state["profile"] = db.get_profile(client, user.id) or {"rol": "supervisor"}
        st.rerun()
    except Exception as e:
        st.error(f"No se pudo iniciar sesión: {e}")
