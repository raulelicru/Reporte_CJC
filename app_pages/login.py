"""Pantalla de login (§7). Login propio contra Neon (tabla usuarios) o modo demo.

Si la base está configurada pero no hay usuarios todavía, muestra el alta del
primer administrador (bootstrap) para no depender de SQL manual.
"""
import streamlit as st

from cobranza import db
from cobranza.demo import build_demo


def render():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('<div style="text-align:center;margin-top:8vh">'
                    '<div style="font-family:Fraunces,serif;font-size:1.8rem;font-weight:600">Consultores CRZ</div>'
                    '<div class="eyebrow">Inteligencia de Cobranza</div></div>', unsafe_allow_html=True)

        configured = db.is_configured()
        needs_bootstrap = False
        if configured:
            try:
                needs_bootstrap = db.count_users() == 0
            except Exception as e:
                st.error(f"No se pudo conectar a la base (DATABASE_URL): {e}")
                configured = False

        with st.container(border=True):
            if not configured:
                st.info("La base (Neon) no está configurada. Explora todo en **modo demo** con datos sintéticos.")
            elif needs_bootstrap:
                _bootstrap_admin()
            else:
                _login()

            if st.button("Entrar en modo demo (datos sintéticos)", use_container_width=True):
                st.session_state["demo"] = True
                st.session_state["authed"] = True
                st.session_state["store"] = build_demo()
                st.session_state["profile"] = {"rol": "admin", "nombre": "Demo", "org_id": db.DEFAULT_ORG}
                st.rerun()

        st.caption("Acceso restringido. Sin sesión no se entra a ninguna vista.")


def _login():
    email = st.text_input("Correo", placeholder="tu@correo.com")
    password = st.text_input("Contraseña", type="password")
    if st.button("Entrar", type="primary", use_container_width=True):
        if not email or not password:
            st.error("Ingresa correo y contraseña.")
            return
        try:
            sesion = db.sign_in(email, password)
        except Exception as e:
            st.error(f"Error de conexión: {e}")
            return
        if not sesion:
            st.error("Credenciales inválidas.")
            return
        _entrar(sesion)


def _bootstrap_admin():
    st.warning("No hay usuarios todavía. Crea el **primer administrador**.")
    nombre = st.text_input("Nombre")
    email = st.text_input("Correo", placeholder="tu@correo.com")
    password = st.text_input("Contraseña", type="password")
    password2 = st.text_input("Repite la contraseña", type="password")
    if st.button("Crear administrador", type="primary", use_container_width=True):
        if not email or not password:
            st.error("Correo y contraseña son obligatorios.")
            return
        if password != password2:
            st.error("Las contraseñas no coinciden.")
            return
        try:
            db.create_user(email, password, rol="admin", nombre=nombre or email)
            sesion = db.sign_in(email, password)
            _entrar(sesion)
        except Exception as e:
            st.error(f"No se pudo crear el usuario: {e}")


def _entrar(sesion: dict):
    st.session_state["authed"] = True
    st.session_state["demo"] = False
    st.session_state["user_id"] = sesion["id"]
    st.session_state["profile"] = {"rol": sesion["rol"], "nombre": sesion["nombre"],
                                   "org_id": sesion["org_id"], "email": sesion["email"]}
    st.rerun()
