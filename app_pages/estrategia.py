"""Estrategia — analítica avanzada (hazard corregido, esfuerzo-retorno, timing)."""
import pandas as pd
import streamlit as st

from cobranza import ui
from cobranza.analytics import COSTOS_DEFAULT, roi_recompute
from cobranza.charts import bar_list, heatmap_timing, mirror_bars
from cobranza.format import money, money_k, num, pct


def _descargar_informe(actual, e):
    from cobranza.report import build_report_html
    d = ui.data()
    ctx = {
        "brand": ui.brand_of(actual), "campaign": actual,
        "resumen": d.resumen(actual["id"]), "canal": d.canal(actual["id"]),
        "agentes": d.agentes(actual["id"]), "estrategia": e,
    }
    try:
        html = build_report_html(ctx)
    except Exception as ex:  # nunca romper la página por el informe
        st.caption(f"Informe no disponible: {ex}")
        return
    nombre = f'informe_{actual.get("anio_campania","")}_{actual.get("fecha_snapshot","")}.html'
    st.download_button("⬇ Descargar informe HTML", data=html, file_name=nombre,
                       mime="text/html", type="primary")


def render():
    actual, _ = ui.require_campaign()
    e = ui.data().estrategia(actual["id"])
    if not e or not e.get("disponible"):
        st.info("La analítica de estrategia se calcula al confirmar la campaña. Vuelve a cargarla para generarla.")
        st.stop()

    ui.page_header("Estrategia · analítica avanzada",
                   "¿Qué gestión produce el pago y dónde se desperdicia el esfuerzo?",
                   "Corregido por sesgo de truncamiento (panel día-a-día). Correlación controlada por tiempo en riesgo — no causa, pero honesto.")

    _descargar_informe(actual, e)

    u = e["universo"]
    v = e["ventana"]
    c = st.columns(4)
    c[0].metric("Universo evaluable", num(u["evaluables"]))
    c[1].metric("Excluidas pre-ventana", num(u["pre_ventana_excluidas"]))
    c[2].metric("Ventana de gestión", f'{v["inicio"]} → {v["corte"]}')
    c[3].metric("Lookback atribución", f'{v["lookback"]} días')

    # ── El titular: esfuerzo vs. dinero ──
    er = e["esfuerzo_retorno"]
    if er:
        ui.section("¿Dónde está mal dirigido el esfuerzo?", "El titular",
                   "Barras espejo: reparto del esfuerzo (izquierda) contra reparto del dinero recuperado (derecha), por tramo. Si están invertidas, ahí está la fuga.")
        st.markdown(mirror_bars(er, "pct_esfuerzo", "pct_recuperado", "temp",
                                "% del esfuerzo", "% del dinero"), unsafe_allow_html=True)
        df = pd.DataFrame([{
            "Tramo": r["temp"], "Gestiones": r["gestiones"], "% esfuerzo": round(r["pct_esfuerzo"] * 100, 1),
            "Recuperado": round(r["recuperado"]), "% dinero": round(r["pct_recuperado"] * 100, 1),
            "$/gestión": round(r["pesos_por_gestion"], 1),
            "gest/pago": round(r["gestiones_por_pago"], 1) if r["gestiones_por_pago"] else None,
        } for r in er])
        st.dataframe(df, use_container_width=True, hide_index=True)

    ra = e.get("reasignacion")
    if ra:
        ui.callout("warn", "Escenario de reasignación (supuestos pesimistas)",
                   f"Mover el esfuerzo de <b>{ra['peor']}</b> (menos eficiente) a <b>{ra['mejor']}</b>: "
                   f"libera {num(ra['gestiones_liberadas'])} gestiones ({pct(ra['pct_capacidad'])} de capacidad), "
                   f"sacrifica {money(ra['sacrificada'])}, suma {money(ra['adicional'])} "
                   f"(al {pct(ra['eficiencia_receptor'],0)} de eficiencia del receptor) → "
                   f"<b>neto {money(ra['neto'])}</b> ({pct(ra['neto_pct'])} del total).")

    # ── La joya metodológica: truncamiento ──
    ui.section("Sesgo de truncamiento: la curva que engaña vs. la honesta", "Metodología",
               "La gestión se detiene cuando la dama paga, así que “más gestiones = menos pago” es un espejismo. El panel día-a-día lo corrige.")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<span class="chip" style="background:#FDF1F4;color:#B03A5A">No usar para decidir</span>', unsafe_allow_html=True)
        st.caption("Ingenua — tasa de pago por nº de gestiones (por dama). Sesgada por truncamiento.")
        st.markdown(bar_list([{"label": r["bucket"], "value": r["tasa"], "fill": "fill-espontaneo",
                               "right": f'{pct(r["tasa"])} · n={num(r["damas"])}'} for r in e["truncamiento"]["ingenua"]],
                             max_value=max([r["tasa"] for r in e["truncamiento"]["ingenua"]] + [0.01])), unsafe_allow_html=True)
    with col2:
        st.markdown('<span class="chip chip-mentor">Corregida</span>', unsafe_allow_html=True)
        st.caption("Hazard diario por dosis previa (panel día-a-día). Cada dosis sube la probabilidad diaria de pago.")
        st.markdown(bar_list([{"label": r["bucket"], "value": r["hazard"], "fill": "fill-llamada",
                               "right": f'{pct(r["hazard"],2)} · {num(r["dias_riesgo"])} días'} for r in e["truncamiento"]["corregida"]],
                             max_value=max([r["hazard"] for r in e["truncamiento"]["corregida"]] + [0.01])), unsafe_allow_html=True)

    # ── Hazard por canal ──
    ui.section("Efecto aislado por canal", "Canal · a igual día de riesgo",
               "Probabilidad diaria de pago CON exposición al canal en los días previos vs. SIN ella. El lift es el efecto asociado, controlando el tiempo en riesgo.")
    hc = e["hazard_canal"]
    st.markdown(bar_list([{"label": r["canal"], "value": max(0, r["lift"]),
                           "fill": {"Llamada": "fill-llamada", "IVR": "fill-ivr", "SMS": "fill-sms"}[r["canal"]],
                           "right": f'con {pct(r["hazard_con"],2)} · sin {pct(r["hazard_sin"],2)} · lift {r["lift"]*100:+.2f}pp'}
                          for r in hc], max_value=max([abs(r["lift"]) for r in hc] + [0.01])), unsafe_allow_html=True)
    neg = [r for r in hc if r["lift"] < 0]
    if neg:
        ui.callout("info", "Hallazgo incómodo (honesto)",
                   f"{', '.join(r['canal'] for r in neg)} muestra lift negativo: la exposición se asocia a MENOR pago. "
                   "Casi siempre es selección (el canal se manda a las cuentas más difíciles), no daño. Para probar causa haría falta un grupo de control.")

    # ── Timing ──
    tm = e.get("timing", {})
    if tm.get("disponible"):
        ui.section("Contactabilidad por día y hora", "Timing",
                   "La franja horaria que el prompt creía imposible — sale de la hora del crudo (Vicidial/IVR). Verde = mayor tasa de contacto efectivo.")
        st.markdown(heatmap_timing(tm["celdas"]), unsafe_allow_html=True)
        if tm.get("mejor"):
            m = tm["mejor"]
            st.caption(f"Mejor franja con volumen: {m['dow_lbl']} {m['hora']}:00 — {pct(m['tasa'])} de contacto ({num(m['efectivos'])}/{num(m['toques'])}).")

    # ── ROI en pesos por canal ──
    _roi(e)

    st.divider()
    st.caption("Fase A + B del roadmap elite: hazard corregido, timing, modelos, roll-rate, segmentación, "
               "correlación y ROI en pesos. Pendiente champion/challenger (requiere grupo de control).")


def _roi(e):
    roi = e.get("roi") or {}
    vols = roi.get("volumenes")
    if not roi.get("disponible") or not vols:
        return
    ui.section("ROI en pesos por canal", "Retorno sobre costo",
               "Recuperación atribuida (último toque) contra el costo del canal. Los costos unitarios son editables: "
               "muévelos a los de tu operación y el retorno se recalcula al instante.")
    base = roi.get("costos") or COSTOS_DEFAULT
    with st.expander("Ajustar costos unitarios (pesos)"):
        c = st.columns(4)
        costos = {
            "Llamada": c[0].number_input("$ / gestión (Llamada)", min_value=0.0, value=float(base["Llamada"]), step=0.5),
            "IVR": c[1].number_input("$ / intento (IVR)", min_value=0.0, value=float(base["IVR"]), step=0.05, format="%.2f"),
            "SMS": c[2].number_input("$ / mensaje (SMS)", min_value=0.0, value=float(base["SMS"]), step=0.05, format="%.2f"),
            "marcador_min": c[3].number_input("$ / min marcador (C3)", min_value=0.0, value=float(base["marcador_min"]), step=0.05, format="%.2f"),
        }
    r = roi_recompute(vols, costos)

    cols = st.columns(3)
    cols[0].metric("Recuperado atribuido", money_k(r["recuperado_total"]))
    cols[1].metric("Costo estimado", money_k(r["costo_total"]))
    cols[2].metric("ROI global", f'{r["roi_total"]:.1f}×' if r["roi_total"] else "—",
                   delta=f'neto {money_k(r["neto_total"])}')
    df = pd.DataFrame([{
        "Canal": f["canal"], "Intentos": f["intentos"], "Efectivos": f["efectivos"],
        "$ unitario": round(f["costo_unitario"], 2), "Costo": round(f["costo"]),
        "Recuperado (atrib.)": round(f["recuperado"]),
        "Neto": round(f["neto"]), "ROI": f'{f["roi"]:.1f}×' if f["roi"] else "—",
        "Costo/$ recup.": f'{f["costo_por_peso"]:.3f}' if f["costo_por_peso"] else "—",
    } for f in r["filas"]])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown(bar_list([{"label": f["canal"], "value": max(0.0, f["roi"] or 0),
                           "fill": {"Llamada": "fill-llamada", "IVR": "fill-ivr", "SMS": "fill-sms"}[f["canal"]],
                           "right": f'{money(f["recuperado"])} ÷ {money(f["costo"])} = {f["roi"]:.1f}×' if f["roi"] else "sin costo"}
                          for f in r["filas"]],
                         max_value=max([(f["roi"] or 0) for f in r["filas"]] + [1.0])), unsafe_allow_html=True)
    if r["costo_marcador"] > 0:
        st.caption(f'El costo del marcador automático (C3) es {money(r["costo_marcador"])} y se carga al canal Llamada. '
                   "Atribución por último toque: es una foto con supuestos explícitos, no contabilidad.")
