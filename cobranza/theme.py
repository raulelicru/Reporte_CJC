"""Identidad visual §9 — tema claro, editorial, sobrio. Se inyecta como CSS."""
from __future__ import annotations

import streamlit as st

# Tokens (§9)
BG = "#FBFAF7"
PANEL = "#FFFFFF"
INK = "#16202E"
INK70 = "#5A6472"
LINE = "#E4E8EE"
AMBER = "#B77E17"  # Llamada
TEAL = "#12A99A"   # SMS
ROSE = "#D6486A"   # IVR
GRAY = "#8A94A3"   # Espontáneo

CANAL_COLOR = {"Llamada": AMBER, "IVR": ROSE, "SMS": TEAL, "Espontaneo": GRAY}

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

.stApp {{ background: {BG}; }}
html, body, [class*="css"] {{ font-family: Inter, system-ui, sans-serif; color: {INK}; }}
h1, h2, h3 {{ font-family: Fraunces, Georgia, serif; letter-spacing: -0.01em; color: {INK}; }}

.num, .tabular {{ font-family: 'JetBrains Mono', ui-monospace, monospace; font-variant-numeric: tabular-nums; }}
.eyebrow {{ font-size: .7rem; letter-spacing: .12em; text-transform: uppercase; color: {INK70}; font-weight: 600; }}

.panel {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px; padding: 16px; }}
.kpi-val {{ font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; font-size: 1.6rem; font-weight: 600; }}

.bar-row {{ display: grid; grid-template-columns: 140px 1fr auto; align-items: center; gap: 12px; padding: 6px 0; }}
.bar-track {{ position: relative; height: 22px; background: #F1F0EB; border-radius: 5px; overflow: hidden; }}
.bar-fill {{ position: absolute; top:0; bottom:0; left:0; border-radius: 5px; }}
.fill-llamada {{ background: {AMBER}; }} .fill-ivr {{ background: {ROSE}; }}
.fill-sms {{ background: {TEAL}; }} .fill-espontaneo {{ background: {GRAY}; }}

.tag {{ display:inline-flex; align-items:center; gap:6px; font-size:.8rem; font-weight:500; }}
.dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}

.callout {{ display:flex; gap:12px; padding:14px 16px; border-radius:10px; border:1px solid {LINE}; background:#fff; margin:6px 0; }}
.callout.warn {{ border-color:#ECD9B0; background:#FDF8EE; }}
.callout.crit {{ border-color:#F0C6D1; background:#FDF1F4; }}

.chip {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:.72rem; font-weight:600; border:1px solid {LINE}; }}
.chip-mentor {{ background:#EAFAF4; color:#0C7A6F; border-color:#B8E6DA; }}
.chip-coaching {{ background:#FDF8EE; color:#9A6A12; border-color:#ECD9B0; }}
.chip-volumen {{ background:#EEF3FB; color:#2B5C9A; border-color:#CFE0F5; }}
.chip-plan {{ background:#FDF1F4; color:#B03A5A; border-color:#F0C6D1; }}

[data-testid="stSidebar"] {{ background: {PANEL}; border-right: 1px solid {LINE}; }}
</style>
"""


def inject():
    st.markdown(_CSS, unsafe_allow_html=True)


CHIP_CLASS = {
    "MENTOR": "chip-mentor",
    "COACHING_CIERRE": "chip-coaching",
    "SUBIR_VOLUMEN": "chip-volumen",
    "PLAN_MEJORA": "chip-plan",
}
