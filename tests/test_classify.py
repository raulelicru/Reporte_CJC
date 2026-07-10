"""Cobertura de la clasificación de gestores (§6)."""
from cobranza.classify import (
    GestorClasificado,
    GestorInput,
    UMBRAL_CUMPLIMIENTO_DEBIL,
    clasificar_equipo,
    emparejar_mentores,
    mediana,
    percentil,
)


def g(agente_id, gestiones, contactos, pdp, cumplidas, recuperado=0.0):
    return GestorInput(agente_id, agente_id, gestiones, contactos, pdp, cumplidas, recuperado)


def test_mediana():
    assert mediana([1, 2, 3]) == 2
    assert mediana([1, 2, 3, 4]) == 2.5
    assert mediana([]) == 0


def test_percentil():
    assert abs(percentil(3, [1, 2, 3, 4]) - 0.625) < 1e-9


def _equipo():
    return clasificar_equipo(
        [
            g("A", 100, 80, 20, 16),  # 0.80 / 0.80 → MENTOR
            g("B", 100, 75, 20, 4),   # 0.75 / 0.20 → COACHING
            g("C", 100, 30, 20, 18),  # 0.30 / 0.90 → SUBIR VOLUMEN
            g("D", 100, 20, 20, 2),   # 0.20 / 0.10 → PLAN MEJORA
        ]
    )


def test_cuadrantes():
    by = {x.agente_id: x for x in _equipo()}
    assert by["A"].clasificacion == "MENTOR"
    assert by["B"].clasificacion == "COACHING_CIERRE"
    assert by["C"].clasificacion == "SUBIR_VOLUMEN"
    assert by["D"].clasificacion == "PLAN_MEJORA"


def test_plan_mejora_recibe_mentor():
    by = {x.agente_id: x for x in _equipo()}
    assert by["D"].mentor_sugerido == "A"


def test_cumplimiento_debil():
    by = {x.agente_id: x for x in _equipo()}
    assert by["B"].cumplimiento_debil is True  # 0.20 < 0.32
    assert by["A"].cumplimiento_debil is False
    assert abs(UMBRAL_CUMPLIMIENTO_DEBIL - 0.32) < 1e-9


def test_umbrales_relativos_a_mediana():
    r = clasificar_equipo(
        [
            g("A", 100, 95, 20, 19),
            g("B", 100, 94, 20, 18),
            g("C", 100, 60, 20, 10),
            g("D", 100, 55, 20, 9),
        ]
    )
    m = {x.agente_id: x for x in r}
    # C tiene 0.60 (alto en absoluto) pero bajo vs el equipo fuerte.
    assert m["C"].contacto_alto is False


def test_sin_mentor_plan_mejora_sin_sugerencia():
    def clasificado(agente_id, clasificacion):
        return GestorClasificado(
            agente_id=agente_id, nombre=agente_id, gestiones=0, contactos_efectivos=0,
            pdp=0, pdp_cumplidas=0, recuperado_atribuido=0.0, tasa_contacto=0.0,
            pct_cumplimiento=0.0, rendimiento=0.0, contacto_alto=False,
            cumplimiento_alto=False, cumplimiento_debil=True, clasificacion=clasificacion,
            percentil_contacto=0.0, percentil_cumplimiento=0.0,
        )

    lista = [clasificado("X", "PLAN_MEJORA"), clasificado("Y", "COACHING_CIERRE")]
    r = emparejar_mentores(lista)
    assert next(x for x in r if x.agente_id == "X").mentor_sugerido is None
