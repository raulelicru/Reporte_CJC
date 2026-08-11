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

    _nueva_cartera(actual, d)

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


def _nueva_cartera(actual, d):
    """Cartera no tocada y sin pago → descargable como una NUEVA cartera."""
    brand = ui.brand_of(actual)
    e = d.estrategia(actual["id"]) or {}
    cn = e.get("cartera_nueva") if e.get("disponible") else None
    if not cn:
        return

    ui.section("Nueva cartera a trabajar", "Cuentas sin tocar y sin pago",
               f'{brand.unidad_cap}s que no recibieron ni un contacto efectivo y tampoco pagaron. '
               "Entran limpias al siguiente ciclo — descárgalas como una nueva cartera.")
    cols = st.columns(3)
    cols[0].metric(f"{brand.unidad_cap}s sin trabajar", num(cn["cuentas"]))
    cols[1].metric("Saldo sin trabajar", money_k(cn["saldo_total"]))
    cols[2].metric("% de la cartera", pct(cn.get("pct_cuentas", 0)))

    if cn["cuentas"] == 0:
        st.success("Toda la cartera fue tocada o pagó: no hay cuentas para relanzar.")
        return

    from cobranza.export import cartera_nueva_xlsx, cartera_nueva_filename
    xlsx = cartera_nueva_xlsx(cn, brand, actual)
    st.download_button(
        f"⬇ Descargar nueva cartera ({num(cn['cuentas'])} {brand.unidad_plural})",
        data=xlsx, file_name=cartera_nueva_filename(brand, actual),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    with st.expander(f"Ver las {num(min(cn['cuentas'], 50))} de mayor saldo"):
        import pandas as pd
        top = cn["filas"][:50]
        df = pd.DataFrame([{
            brand.unidad_cap: f["num_dama"], "Saldo": round(f["saldo"] or 0),
            "Zona": f.get("zona"), "Ruta": f.get("ruta"), "Temporalidad": f.get("temporalidad") or "—",
        } for f in top])
        st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Definición: sin contacto efectivo (ningún canal conectó) y sin pago recuperado. "
               "El archivo trae Num, saldo, zona, ruta y temporalidad, listo para re-subir o entregar.")


def _g(previo, key):
    return previo.get(key) if previo else None
