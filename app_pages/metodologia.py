"""Metodología (§8 pág. 11) — siempre accesible."""
import streamlit as st

from cobranza import ui


def render():
    ui.page_header("Siempre accesible", "Metodología",
                   "Cómo se lee cada número. Si algo aquí contradice la intuición de “cómo se hace un dashboard”, gana esta página: la lógica de atribución se validó sobre 1.5M de registros reales.")

    ui.section("Contacto efectivo ≠ intento", "C1")
    st.markdown("Solo cuenta el toque que conectó. Gestiones `TIPO DE GESTION = CONTACTO`; IVR `Status = Contacto`; SMS `Descripcion ∈ {Exitoso, Enviado}`. Un marcado que no conecta nunca recibe atribución.")

    ui.section("Gestiones y Vicidial = un solo canal", "C2")
    st.markdown("Los gestores del CRM coinciden por nombre normalizado (minúsculas, sin acentos, trim) con los agentes de Vicidial. El marcador conecta la llamada; el CRM captura resultado y promesa. Se fusionan en **Llamada** para no duplicar la recuperación.")

    ui.section("El marcador automático es costo, no canal", "C3")
    st.markdown("`full_name ∈ {Outbound Auto Dial, Inbound No Agent}` se contabiliza como costo de telefonía (llamadas, minutos), con cero contactos efectivos. Nunca aparece como recuperación.")

    ui.section("Prohibido inflar causalidad", "C4")
    st.markdown("Un pago sin contacto efectivo previo es **Espontáneo**, jamás atribuible al canal que lo marcó y no conectó. Toda métrica de canal es **correlación, no causa**: sin grupo de control no se aísla el efecto del recordatorio.")

    ui.section("Atribución: último toque efectivo", "Modelo")
    st.markdown("""
- Cada pago se asigna al último canal con contacto efectivo en o antes de la fecha de pago.
- Ventana de 7 días. Empate el mismo día: Llamada > IVR > SMS.
- Sin toque en la ventana ⇒ Espontáneo.
- Modelo secundario (influencia any-touch): % del monto de consultoras con ≥1 contacto efectivo de cada canal. Suma más de 100% y se reporta aparte.
""")

    ui.section("Sesgo temporal", "Límite")
    st.markdown("Si los pagos se extienden más allá de la última fecha de datos de canal, ese tramo no puede recibir atribución y entra como espontáneo por construcción. Se muestra como alerta metodológica, no como hallazgo de negocio.")

    ui.section("Recuperado", "Monto")
    st.markdown("`Recuperado = SaldoCobro (cartera) − SaldoCampania (remanente)` por `Dama-deuda`, solo para llaves que cruzan con la cartera cargada.")

    ui.section("Campos no usables / trampas de ingesta", "Fuentes")
    st.markdown("""
- `FechaEntrega` entero `YYYYMMDD`, parseado explícito.
- Pagos incluye campañas anteriores (ej. C11): se filtra a la cartera cargada.
- `EstadoProceso` R y E, ambos con remanente 0 = liquidación (catálogo abierto).
- Cartera dedup por `Dama-deuda` conservando la última `FechaEntrega`.
- `MEDICION` ~99.97% vacía → inutilizable, no se muestra.
- IVR sin fecha parseable → excluidas de atribución, contadas aparte.
- SMS `Dama` texto → coacción a int, nulos descartados.
- Encoding roto (`Ã³`/`Ã±`) se reporta como flag de calidad.
- **Camino de Crecimiento** (Bronce/Plata/Oro/Diamante) NO existe en las fuentes; hook nullable dejado, sin inventar el corte.
""")

    ui.section("Clasificación de gestores", "Talento")
    st.markdown("Umbrales relativos a la mediana del equipo en cada campaña. Cuadrante contacto × cumplimiento: Mentor, Coaching de cierre, Subir volumen, Plan de mejora. Cumplimiento < ~32% ⇒ coaching, nunca despido automático. A cada plan de mejora se le sugiere un mentor. Lenguaje de desarrollo de talento.")
