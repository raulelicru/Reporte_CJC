"""Usuarios (solo admin) — crear cuentas de acceso, ver la lista y asignar rol."""
import pandas as pd
import streamlit as st

from cobranza import db, ui

ROLES = ["admin", "gerente", "supervisor"]
ROL_AYUDA = {
    "admin": "Acceso total: carga de datos y gestión de usuarios.",
    "gerente": "Solo lectura de todos los tableros.",
    "supervisor": "Solo lectura de todos los tableros.",
}


def render():
    if not ui.is_admin():
        st.warning("Solo el rol admin puede gestionar usuarios.")
        st.stop()

    ui.page_header("Solo admin", "Usuarios",
                   "Crea cuentas de acceso a la plataforma, revisa quién tiene acceso y asigna su rol.")

    if st.session_state.get("demo"):
        st.info("Estás en **modo demo**: no hay base conectada, así que no se pueden crear usuarios reales. "
                "Entra con tu cuenta real (Neon configurado) para gestionar accesos.")
        st.stop()

    if not db.is_configured():
        st.info("La base (Neon) no está configurada: no se pueden gestionar usuarios. Rellena DATABASE_URL en los secrets.")
        st.stop()

    prof = st.session_state.get("profile") or {}
    org_id = prof.get("org_id", db.DEFAULT_ORG)

    # ── Usuarios existentes ──
    try:
        usuarios = db.list_users(org_id)
    except Exception as e:
        st.error(f"No se pudo leer la lista de usuarios: {e}")
        st.stop()

    ui.section(f"Usuarios con acceso ({len(usuarios)})")
    if usuarios:
        df = pd.DataFrame([{
            "Nombre": u.get("nombre") or "—", "Correo": u["email"],
            "Rol": u["rol"], "Equipo": u.get("equipo") or "—",
            "Creado": (u.get("created_at") or "")[:10],
        } for u in usuarios])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("Aún no hay usuarios en esta organización.")

    emails = {u["email"].lower() for u in usuarios}

    # ── Crear / actualizar usuario ──
    ui.section("Crear una cuenta nueva")
    with st.form("crear_usuario", clear_on_submit=False):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre")
        email = c2.text_input("Correo", placeholder="persona@correo.com")
        c3, c4, c5 = st.columns(3)
        rol = c3.selectbox("Rol", ROLES, help=" · ".join(f"{k}: {v}" for k, v in ROL_AYUDA.items()))
        password = c4.text_input("Contraseña", type="password")
        password2 = c5.text_input("Repite la contraseña", type="password")
        st.caption(ROL_AYUDA.get(rol, ""))
        enviar = st.form_submit_button("Crear cuenta", type="primary")

    if enviar:
        email_n = (email or "").strip().lower()
        if not email_n or not password:
            st.error("Correo y contraseña son obligatorios.")
            return
        if "@" not in email_n or "." not in email_n:
            st.error("El correo no parece válido.")
            return
        if len(password) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
            return
        if password != password2:
            st.error("Las contraseñas no coinciden.")
            return
        existe = email_n in emails
        try:
            db.create_user(email_n, password, rol=rol, nombre=nombre or email_n, org_id=org_id)
        except Exception as e:
            st.error(f"No se pudo crear la cuenta: {e}")
            return
        if existe:
            st.success(f"Ese correo ya existía: se **restableció la contraseña** de {email_n}.")
        else:
            st.success(f"Cuenta creada para {email_n} con rol {rol}. Ya puede iniciar sesión.")
        st.rerun()

    st.caption("Nota: si el correo ya existe, esta acción solo restablece su contraseña (no cambia su rol). "
               "Las contraseñas se guardan cifradas (bcrypt); nadie las ve en claro.")
