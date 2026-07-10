"""Helpers de UI compartidos y acceso a datos (demo o Supabase)."""
from __future__ import annotations

import html

import streamlit as st

from . import db
from .format import delta, dias_entre


# ──────────────────────────────────────────────────────────────────────────
# Acceso a datos: en modo demo lee de un store en memoria; con Supabase lee de
# las tablas (RLS aplica con el cliente autenticado). Misma interfaz para la UI.
# ──────────────────────────────────────────────────────────────────────────
class Data:
    def __init__(self):
        self.demo = st.session_state.get("demo", False)
        self.store = st.session_state.get("store")
        self.client = st.session_state.get("client")

    def campaigns(self):
        if self.demo:
            return self.store["campaigns"]
        return db.get_campaigns(self.client)

    def _d(self, cid, key):
        return self.store["data"].get(cid, {}).get(key)

    def resumen(self, cid):
        return self._d(cid, "resumen") if self.demo else db.get_resumen(self.client, cid)

    def canal(self, cid):
        return self._d(cid, "canal") if self.demo else db.get_canal(self.client, cid)

    def agentes(self, cid):
        return self._d(cid, "agentes") if self.demo else db.get_agentes(self.client, cid)

    def temporalidad(self, cid):
        return self._d(cid, "temporalidad") if self.demo else db.get_temporalidad(self.client, cid)

    def diaria(self, cid):
        return self._d(cid, "diaria") if self.demo else db.get_diaria(self.client, cid)

    def secuencias(self, cid):
        return self._d(cid, "secuencias") if self.demo else db.get_secuencias(self.client, cid)

    def flags(self, cid):
        return self._d(cid, "flags") if self.demo else db.get_quality_flags(self.client, cid)

    def costo_marcador(self, cid):
        return self._d(cid, "costo_marcador") if self.demo else db.get_costo_marcador(self.client, cid)

    def historia(self):
        return self.store["historia"] if self.demo else db.get_historia_gestores(self.client)

    def comparativa(self):
        if not self.demo:
            return db.get_comparativa(self.client)
        camps = self.store["campaigns"]
        return {
            "campaigns": camps,
            "resumenes": [{"campaign_id": c["id"], **self.store["data"][c["id"]]["resumen"]} for c in camps],
            "canales": [{"campaign_id": c["id"], **row} for c in camps for row in self.store["data"][c["id"]]["canal"]],
            "cumplimiento": {c["id"]: _avg_cumpl(self.store["data"][c["id"]]["agentes"]) for c in camps},
        }

    def resumen_previo(self, campaigns, actual):
        # Snapshot anterior de la MISMA campaña (día previo). Si no hay foto
        # previa de esa campaña, el delta queda vacío.
        mismos = [
            c for c in campaigns
            if c["anio_campania"] == actual["anio_campania"]
            and (c.get("fecha_snapshot") or "") < (actual.get("fecha_snapshot") or "")
        ]
        if not mismos:
            return None
        prev = max(mismos, key=lambda c: c.get("fecha_snapshot") or "")
        return self.resumen(prev["id"])


def _avg_cumpl(agentes):
    pdp = sum(a["pdp"] for a in agentes)
    cumpl = sum(a["pdp_cumplidas"] for a in agentes)
    return cumpl / pdp if pdp else 0.0


def data() -> Data:
    return Data()


def selected_campaign():
    d = data()
    camps = d.campaigns()
    if not camps:
        return None, camps
    cid = st.session_state.get("cid")
    actual = next((c for c in camps if c["id"] == cid), camps[0])
    st.session_state["cid"] = actual["id"]
    return actual, camps


def require_campaign():
    actual, camps = selected_campaign()
    if actual is None:
        st.info("No hay campañas cargadas. Ve a **Carga de datos** (admin) o entra en modo demo.")
        st.stop()
    return actual, camps


def is_admin() -> bool:
    if st.session_state.get("demo"):
        return True
    prof = st.session_state.get("profile") or {}
    return prof.get("rol") == "admin"


# ──────────────────────────────────────────────────────────────────────────
# Componentes de render (HTML propio, identidad §9)
# ──────────────────────────────────────────────────────────────────────────
def page_header(eyebrow: str, title: str, desc: str | None = None):
    st.markdown(f'<div class="eyebrow">{html.escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.markdown(f"## {title}")
    if desc:
        st.markdown(f'<p style="color:#5A6472;font-size:.9rem;max-width:48rem">{html.escape(desc)}</p>', unsafe_allow_html=True)


def section(title: str, eyebrow: str | None = None, desc: str | None = None):
    if eyebrow:
        st.markdown(f'<div class="eyebrow" style="margin-top:8px">{html.escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.markdown(f"### {title}")
    if desc:
        st.markdown(f'<p style="color:#5A6472;font-size:.88rem;max-width:48rem">{html.escape(desc)}</p>', unsafe_allow_html=True)


def kpi(label: str, value: str, sub: str | None = None, actual=None, previo=None, invert=False):
    d = delta(actual, previo) if actual is not None else None
    tail = ""
    if sub:
        tail += f'<span style="color:#5A6472;font-size:.75rem">{html.escape(sub)}</span> '
    if d:
        good = None if d["signo"] == "flat" else (d["signo"] == "up") != invert
        color = "#5A6472" if good is None else ("#12A99A" if good else "#D6486A")
        arrow = "▲" if d["signo"] == "up" else "▼" if d["signo"] == "down" else ""
        tail += f'<span class="num" style="color:{color};font-size:.75rem">{arrow} {d["texto"]}<span style="color:#5A6472"> vs. anterior</span></span>'
    st.markdown(
        f'<div class="panel"><div class="eyebrow" style="margin-bottom:6px">{html.escape(label)}</div>'
        f'<div class="kpi-val">{html.escape(value)}</div><div style="margin-top:4px">{tail}</div></div>',
        unsafe_allow_html=True,
    )


def callout(tone: str, title: str, body: str):
    st.markdown(
        f'<div class="callout {tone}"><div><div style="font-weight:600;font-size:.9rem">{title}</div>'
        f'<div style="color:#5A6472;font-size:.88rem;margin-top:2px">{body}</div></div></div>',
        unsafe_allow_html=True,
    )


def correlacion_nota():
    st.markdown('<span class="chip" style="background:#F4F2EC;color:#5A6472">correlación, no causa</span>', unsafe_allow_html=True)


def campaign_badge(actual):
    madurez = dias_entre(actual.get("fecha_liberacion"), actual.get("fecha_corte_datos"))
    madura = madurez is not None and madurez >= 30
    bg = "#EAFAF4" if madura else "#FDF8EE"
    col = "#0C7A6F" if madura else "#9A6A12"
    txt = f"madurez {madurez if madurez is not None else '?'}d · {'madura' if madura else 'recién liberada'}"
    st.markdown(f'<span class="chip" style="background:{bg};color:{col}">{txt}</span>', unsafe_allow_html=True)
    if not madura:
        st.caption("Comparar contra campañas maduras puede leerse mal.")
