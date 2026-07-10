"""Resumen ejecutivo (§8 pág. 1)."""
import streamlit as st

from cobranza import ui
from cobranza.format import money, money_k, num, pct


def render():
    actual, camps = ui.require_campaign()
    d = ui.data()
    r = d.resumen(actual["id"])
    if not r:
        st.info("Métricas no calculadas para esta campaña.")
        st.stop()
    previo = d.resumen_previo(camps, actual)
    costo = d.costo_marcador(actual["id"]) or {}
    canales = d.canal(actual["id"]) or []

    _snap = actual.get("fecha_snapshot")
    ui.page_header(
        f"Campaña {actual['anio_campania']}" + (f" · snapshot {_snap}" if _snap else ""),
        "Resumen ejecutivo",
    )

    cols = st.columns(3)
    kpis = [
        ("Recuperado", money(r["recuperado"]), None, r["recuperado"], _g(previo, "recuperado"), False),
        ("% del saldo asignado", pct(r["pct_recuperado"]), f"de {money_k(r['saldo_asignado'])}", r["pct_recuperado"], _g(previo, "pct_recuperado"), False),
        ("Deudas liquidadas", num(r["deudas_liquidadas"]), None, r["deudas_liquidadas"], _g(previo, "deudas_liquidadas"), False),
        ("Saldo pendiente", money(r["saldo_pendiente"]), None, r["saldo_pendiente"], _g(previo, "saldo_pendiente"), True),
        ("% pagos sin contacto", pct(r["pct_pagos_sin_contacto"]), "espontáneos", r["pct_pagos_sin_contacto"], _g(previo, "pct_pagos_sin_contacto"), True),
        ("% cartera nunca contactada", pct(r["pct_cartera_no_contactada"]), None, r["pct_cartera_no_contactada"], _g(previo, "pct_cartera_no_contactada"), True),
    ]
    for i, (label, value, sub, act, prev, inv) in enumerate(kpis):
        with cols[i % 3]:
            ui.kpi(label, value, sub, act, prev, inv)

    ui.section("Tres hallazgos que hay que decir antes que cualquier número", "Lo que cambia la lectura")
    c1, c2, c3 = st.columns(3)
    with c1:
        cm = f"{num(costo.get('llamadas', 0))} llamadas y {num(round(costo.get('minutos', 0)))} min del marcador automático, {num(costo.get('contactos_efectivos', 0))} contactos efectivos. Es costo de telefonía, no un canal."
        ui.callout("crit", "El marcador automático = 0 contactos", cm)
    with c2:
        ui.callout("warn", "Gestiones y Vicidial = un solo canal",
                   "El marcador conecta la llamada; el CRM captura resultado y promesa. Se fusionan en <b>Llamada</b> para no duplicar la recuperación.")
    with c3:
        ui.callout("warn", "% de cartera nunca contactada",
                   f"{pct(r['pct_cartera_no_contactada'])} de las consultoras no recibió ni un contacto efectivo. Ese saldo no tuvo oportunidad de gestión.")

    if r["pct_fuera_ventana"] > 0.01:
        ui.callout("warn", "Sesgo temporal declarado",
                   f"{pct(r['pct_fuera_ventana'])} del recuperado ocurrió después de la última fecha con datos de canal ({actual.get('fecha_corte_datos') or 's/f'}). Ese tramo entra como espontáneo por construcción — limitación metodológica, no hallazgo de negocio.")

    ui.section("Recuperado por canal (último toque efectivo)", "Mezcla")
    cc = st.columns(4)
    for i, c in enumerate(canales):
        with cc[i % 4]:
            st.markdown(
                f'<div class="panel"><div class="eyebrow">{c["canal"]}</div>'
                f'<div class="num" style="font-size:1.25rem;font-weight:600">{money_k(c["monto_ultimo_toque"])}</div>'
                f'<div class="num" style="color:#5A6472;font-size:.75rem">{pct(c["pct"])} · {num(c["pagos"])} pagos</div></div>',
                unsafe_allow_html=True)


def _g(previo, key):
    return previo.get(key) if previo else None
