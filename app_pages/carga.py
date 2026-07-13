"""Carga de datos (§8 pág. 10) — solo admin. Perfila antes de confirmar."""
from datetime import date

import streamlit as st

from cobranza import db, ui
from cobranza.ingest import build_ingest, read_sheet
from cobranza.metrics import compute_metrics
from cobranza.format import num, pct

CAMPOS = [
    ("cartera", "Cartera_Campaña_*.xlsx"),
    ("pagos", "Pago_Campaña_*.xlsx"),
    ("gestiones", "Gestiones_*.xlsx"),
    ("vicidial", "Base_Vicidial_*.xlsx"),
    ("ivr", "Base_Reminder_*.xlsx (IVR)"),
    ("sms", "Base_SMS_*.xlsx"),
]


def render():
    if not ui.is_admin():
        st.warning("Solo el rol admin puede cargar campañas.")
        st.stop()

    ui.page_header("Solo admin", "Carga de datos",
                   "Sube los 6 archivos. Primero verás el perfilado y los flags de calidad; nada se persiste hasta que confirmas.")

    col1, col2, col3 = st.columns(3)
    anio = col1.text_input("AnioCampaniaSaldo", placeholder="2025C12")
    nombre = col2.text_input("Nombre", placeholder="Campaña 12 · 2025")
    snapshot = col3.date_input("Fecha del snapshot (día de carga)", value=date.today())
    st.caption("Cada día se cargan los 6 archivos: cada carga es una foto del día. "
               "Recargar el mismo día reemplaza esa foto; otro día crea una nueva y conserva las pasadas.")

    files = {}
    for key, label in CAMPOS:
        files[key] = st.file_uploader(label, type=["xlsx"], key=f"up_{key}")

    todos = all(files[k] is not None for k, _ in CAMPOS)

    if st.button("1 · Perfilar (sin guardar)", disabled=not (todos and anio)):
        try:
            sheets = {k: read_sheet(files[k]) for k, _ in CAMPOS}
            ing = build_ingest(sheets)
            st.session_state["carga_ing"] = ing
            st.session_state["carga_anio"] = anio
            st.session_state["carga_nombre"] = nombre or f"Campaña {anio}"
            st.session_state["carga_snapshot"] = snapshot.isoformat()
        except Exception as e:
            st.error(f"Error al parsear: {e}")
            st.session_state.pop("carga_ing", None)

    ing = st.session_state.get("carga_ing")
    if ing is not None:
        _perfilado(ing)
        if not db.is_configured():
            st.info("La base (Neon) no está configurada: no se puede persistir. Rellena DATABASE_URL en los secrets.")
        elif st.button("2 · Confirmar y calcular métricas", type="primary"):
            try:
                m = compute_metrics(ing)
                prof = st.session_state.get("profile") or {}
                cid = db.persist_campaign(prof.get("org_id", db.DEFAULT_ORG),
                                          st.session_state["carga_anio"], st.session_state["carga_nombre"],
                                          st.session_state.get("user_id"), ing, m,
                                          fecha_snapshot=st.session_state.get("carga_snapshot"))
                st.success(f"Snapshot del {st.session_state.get('carga_snapshot')} persistido ({cid}). Ve al Resumen ejecutivo.")
                st.session_state["cid"] = cid
                st.session_state.pop("carga_ing", None)
            except Exception as e:
                st.error(f"Error al persistir: {e}")


def _perfilado(ing):
    p = ing.profile
    ui.section("Filas por archivo")
    cols = st.columns(len(p["filas"]))
    for col, (k, v) in zip(cols, p["filas"].items()):
        col.metric(k, num(v))

    ui.section("Tasas de cruce")
    c = st.columns(4)
    c[0].metric("Gestiones en cartera", pct(p["cruces"]["gestiones_en_cartera"]))
    c[1].metric("IVR en cartera", pct(p["cruces"]["ivr_en_cartera"]))
    c[2].metric("SMS en cartera", pct(p["cruces"]["sms_en_cartera"]))
    c[3].metric("Corte de datos", p["fecha_corte_datos"] or "s/f")

    cm = p["costo_marcador"]
    ui.callout("crit", "C3 · Marcador automático (costo, no canal)",
               f"{num(cm['llamadas'])} llamadas · {num(round(cm['minutos']))} min · {num(cm['contactos_efectivos'])} contactos efectivos")

    if p["agentes_solo_crm"] or p["agentes_solo_vicidial"]:
        ui.callout("warn", "C2 · Roster divergente",
                   f"Nombres solo en CRM: {len(p['agentes_solo_crm'])}; solo en Vicidial: {len(p['agentes_solo_vicidial'])}. Revisar el match antes de confiar en la atribución por gestor.")

    ui.section(f"Flags de calidad ({len(ing.flags)})")
    if not ing.flags:
        st.caption("Sin flags.")
    for f in ing.flags:
        icon = {"error": "🔴", "warn": "🟡", "info": "⚪"}.get(f["severidad"], "⚪")
        st.markdown(f"{icon} **{f['tipo']}** — {f['detalle']}")
