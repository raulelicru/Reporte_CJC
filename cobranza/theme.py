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

/* ── Animaciones (la app respira, sin marear) ── */
@keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes growX {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
@keyframes popIn {{ 0% {{ opacity: 0; transform: scale(.96); }} 100% {{ opacity: 1; transform: scale(1); }} }}
@keyframes shimmer {{ 0% {{ background-position: -180% 0; }} 100% {{ background-position: 180% 0; }} }}

.panel {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px; padding: 16px;
          animation: fadeUp .5s cubic-bezier(.2,.7,.2,1) both;
          transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease; }}
.panel:hover {{ transform: translateY(-2px); box-shadow: 0 10px 26px -14px rgba(22,32,46,.28); border-color: #D3DAE3; }}
.kpi-val {{ font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; font-size: 1.6rem; font-weight: 600; }}

.bar-row {{ display: grid; grid-template-columns: 140px 1fr auto; align-items: center; gap: 12px; padding: 6px 0; }}
.bar-track {{ position: relative; height: 22px; background: #F1F0EB; border-radius: 5px; overflow: hidden; }}
.bar-fill {{ position: absolute; top:0; bottom:0; left:0; border-radius: 5px;
             transform-origin: left center; animation: growX .7s cubic-bezier(.2,.8,.2,1) both; }}
.fill-llamada {{ background: {AMBER}; }} .fill-ivr {{ background: {ROSE}; }}
.fill-sms {{ background: {TEAL}; }} .fill-espontaneo {{ background: {GRAY}; }}

/* Entrada escalonada de bloques principales (métricas, tablas, gráficos). */
[data-testid="stMetric"], [data-testid="stDataFrame"], [data-testid="stVerticalBlockBorderWrapper"],
.stPlotlyChart, [data-testid="stImage"], [data-testid="stMarkdownContainer"] > svg {{
    animation: fadeUp .5s cubic-bezier(.2,.7,.2,1) both;
}}
[data-testid="stMetric"] {{ transition: transform .18s ease, box-shadow .18s ease; }}
[data-testid="stMetric"]:hover {{ transform: translateY(-2px); box-shadow: 0 10px 24px -16px rgba(22,32,46,.30); }}
svg rect, svg circle {{ transition: opacity .18s ease; }}
svg:hover rect:hover, svg:hover circle:hover {{ opacity: .82; }}

/* ── Apartado de marca (Arabela / Natura) ── */
.brand-hero {{ margin-top: 6px; padding: 12px 14px; border-radius: 12px; color: #fff;
               display: flex; flex-direction: column; gap: 2px; animation: popIn .38s ease both;
               box-shadow: 0 8px 22px -14px rgba(22,32,46,.5); }}
.brand-hero .brand-name {{ font-family: Fraunces, serif; font-size: 1.15rem; font-weight: 600; letter-spacing: -.01em; }}
.brand-hero .brand-unit {{ font-size: .68rem; letter-spacing: .14em; text-transform: uppercase; opacity: .85; }}
.brand-arabela {{ background: linear-gradient(120deg, #B23A6B 0%, #7C2D8A 100%); }}
.brand-natura {{ background: linear-gradient(120deg, #1F8A54 0%, #0E6E63 100%); }}

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
[data-testid="stSidebar"] .stButton button {{ border-radius: 8px; }}

/* Botones con micro-interacción. */
.stButton button {{ transition: transform .14s ease, box-shadow .14s ease, filter .14s ease; }}
.stButton button:hover {{ transform: translateY(-1px); box-shadow: 0 8px 18px -12px rgba(22,32,46,.45); }}
.stButton button:active {{ transform: translateY(0); }}

/* Selector de marca (segmented_control / radio) como toggle limpio. */
[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 6px; }}
[data-testid="stSidebar"] [data-baseweb="segmented-control"] {{ border-radius: 10px; }}
.stDownloadButton button {{ transition: transform .14s ease, box-shadow .14s ease; }}
.stDownloadButton button:hover {{ transform: translateY(-1px); box-shadow: 0 8px 18px -12px rgba(22,32,46,.45); }}

/* Chrome de Streamlit fuera: se ve como producto, no como demo. */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], .stDeployButton, .stAppDeployButton {{ display: none !important; }}
header[data-testid="stHeader"] {{ background: transparent; height: 0; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }}

/* Métricas nativas con la identidad. */
[data-testid="stMetric"] {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px; padding: 12px 14px; }}
[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; font-size: 1.35rem; }}
[data-testid="stMetricLabel"] {{ text-transform: uppercase; letter-spacing: .08em; font-size: .68rem; color: {INK70}; }}

/* Tablas más de tablero. */
[data-testid="stDataFrame"] {{ border-radius: 10px; overflow: hidden; border: 1px solid {LINE}; }}
h1 {{ font-size: 1.9rem; }} h2 {{ font-size: 1.35rem; }} h3 {{ font-size: 1.08rem; }}
hr {{ border-color: {LINE}; }}
a {{ color: {TEAL}; }}

/* Respeta a quien pide menos movimiento. */
@media (prefers-reduced-motion: reduce) {{
  *, .panel, .bar-fill, .brand-hero, [data-testid="stMetric"], [data-testid="stDataFrame"] {{
    animation: none !important; transition: none !important;
  }}
}}
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
