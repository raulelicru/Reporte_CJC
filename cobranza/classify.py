"""CLASIFICACIÓN DE GESTORES (§6) — quién puede capacitar y quién necesita apoyo.

Umbrales RELATIVOS a la mediana del equipo en esa campaña (no fijos). Lenguaje
de desarrollo de talento: la clasificación orienta coaching, nunca despido.

Cuadrante (contacto vs. cumplimiento contra la mediana):
  Contacto ALTO + Cumplimiento ALTO → MENTOR
  Contacto ALTO + Cumplimiento BAJO → COACHING_CIERRE
  Contacto BAJO + Cumplimiento ALTO → SUBIR_VOLUMEN
  Contacto BAJO + Cumplimiento BAJO → PLAN_MEJORA
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median as _median

# Umbral de cumplimiento débil (~32%): compromisos poco firmes ⇒ coaching.
UMBRAL_CUMPLIMIENTO_DEBIL = 0.32

ETIQUETA_CLASIFICACION = {
    "MENTOR": "Mentor — puede capacitar al equipo",
    "COACHING_CIERRE": "Coaching de cierre — contacta bien, promesas flojas",
    "SUBIR_VOLUMEN": "Subir volumen — buen negociador, darle más base",
    "PLAN_MEJORA": "Plan de mejora — acompañamiento cercano",
}


@dataclass
class GestorInput:
    agente_id: str
    nombre: str
    gestiones: int
    contactos_efectivos: int
    pdp: int
    pdp_cumplidas: int
    recuperado_atribuido: float = 0.0


@dataclass
class GestorClasificado:
    agente_id: str
    nombre: str
    gestiones: int
    contactos_efectivos: int
    pdp: int
    pdp_cumplidas: int
    recuperado_atribuido: float
    tasa_contacto: float
    pct_cumplimiento: float
    rendimiento: float
    contacto_alto: bool
    cumplimiento_alto: bool
    cumplimiento_debil: bool
    clasificacion: str
    percentil_contacto: float
    percentil_cumplimiento: float
    mentor_sugerido: str | None = None


def mediana(xs: list[float]) -> float:
    return _median(xs) if xs else 0.0


def percentil(x: float, xs: list[float]) -> float:
    """Percentil (rank fraccional) de x dentro de xs. 0..1."""
    if not xs:
        return 0.0
    menores = sum(1 for v in xs if v < x)
    iguales = sum(1 for v in xs if v == x)
    return (menores + iguales / 2) / len(xs)


def _cuadrante(contacto_alto: bool, cumplimiento_alto: bool) -> str:
    if contacto_alto and cumplimiento_alto:
        return "MENTOR"
    if contacto_alto and not cumplimiento_alto:
        return "COACHING_CIERRE"
    if not contacto_alto and cumplimiento_alto:
        return "SUBIR_VOLUMEN"
    return "PLAN_MEJORA"


def clasificar_equipo(gestores: list[GestorInput]) -> list[GestorClasificado]:
    """Clasifica al equipo completo. Umbrales = mediana; 'alto' ⇒ ≥ mediana."""
    enriquecidos = []
    for g in gestores:
        tasa = g.contactos_efectivos / g.gestiones if g.gestiones > 0 else 0.0
        cumpl = g.pdp_cumplidas / g.pdp if g.pdp > 0 else 0.0
        rend = g.recuperado_atribuido / g.gestiones if g.gestiones > 0 else 0.0
        enriquecidos.append((g, tasa, cumpl, rend))

    contactos = [t for _, t, _, _ in enriquecidos]
    cumplimientos = [c for _, _, c, _ in enriquecidos]
    med_c = mediana(contactos)
    med_k = mediana(cumplimientos)

    clasificados: list[GestorClasificado] = []
    for g, tasa, cumpl, rend in enriquecidos:
        contacto_alto = tasa >= med_c
        cumplimiento_alto = cumpl >= med_k
        clasificados.append(
            GestorClasificado(
                agente_id=g.agente_id,
                nombre=g.nombre,
                gestiones=g.gestiones,
                contactos_efectivos=g.contactos_efectivos,
                pdp=g.pdp,
                pdp_cumplidas=g.pdp_cumplidas,
                recuperado_atribuido=g.recuperado_atribuido,
                tasa_contacto=tasa,
                pct_cumplimiento=cumpl,
                rendimiento=rend,
                contacto_alto=contacto_alto,
                cumplimiento_alto=cumplimiento_alto,
                cumplimiento_debil=cumpl < UMBRAL_CUMPLIMIENTO_DEBIL,
                clasificacion=_cuadrante(contacto_alto, cumplimiento_alto),
                percentil_contacto=percentil(tasa, contactos),
                percentil_cumplimiento=percentil(cumpl, cumplimientos),
            )
        )

    return emparejar_mentores(clasificados)


def emparejar_mentores(clasificados: list[GestorClasificado]) -> list[GestorClasificado]:
    """Empareja cada PLAN_MEJORA con el MENTOR de mayor cumplimiento y capacidad."""
    mentores = sorted(
        (g for g in clasificados if g.clasificacion == "MENTOR"),
        key=lambda g: (g.pct_cumplimiento, g.tasa_contacto, g.gestiones),
        reverse=True,
    )
    mejor = mentores[0].agente_id if mentores else None
    for g in clasificados:
        if g.clasificacion == "PLAN_MEJORA":
            g.mentor_sugerido = mejor
    return clasificados
