"""MOTOR DE ATRIBUCIÓN (§4) — el corazón del sistema.

Funciones PURAS y determinísticas: mismas entradas ⇒ mismas salidas, sin I/O,
sin fecha "hoy", sin aleatoriedad. Testeadas a fondo en tests/test_attribution.py
(C1–C4, empates, ventana de 7 días, sesgo temporal).

Controles antifraude codificados:
  C1 · Contacto efectivo ≠ intento  → solo Touch.efectivo recibe atribución.
  C2 · Gestiones + Vicidial = 1 canal → la ingesta ya emite ambos como "Llamada".
  C3 · Marcador automático = costo   → nunca produce toques efectivos.
  C4 · Prohibido inflar causalidad   → pago sin toque efectivo previo = Espontáneo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

# Canales que sí pueden recibir atribución (excluye Espontáneo).
CANALES_REALES = ("Llamada", "IVR", "SMS")
# Prioridad de desempate el mismo día (Llamada > IVR > SMS) — §4.
PRIORIDAD_CANAL = {"Llamada": 3, "IVR": 2, "SMS": 1}
VENTANA_DIAS = 7


@dataclass(frozen=True)
class Touch:
    num_dama: int
    canal: str  # "Llamada" | "IVR" | "SMS"
    dia: str  # ISO YYYY-MM-DD
    efectivo: bool
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Payment:
    dama_deuda: str
    num_dama: int
    fecha_pago: str  # ISO YYYY-MM-DD
    recuperado: float


@dataclass
class Attribution:
    payment: Payment
    canal: str  # "Llamada" | "IVR" | "SMS" | "Espontaneo"
    touch: Touch | None
    fuera_de_ventana: bool


def dif_dias(a: str, b: str) -> int:
    """Diferencia en días completos entre dos ISO date (a − b)."""
    return (date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days


def attribute_last_touch(payment: Payment, touches_de_la_dama: list[Touch]) -> tuple[str, Touch | None]:
    """MODELO PRIMARIO — último toque efectivo.

    Asigna el pago al último canal con contacto efectivo en la ventana
    [fecha_pago − VENTANA_DIAS, fecha_pago]. Empate el mismo día ⇒ prioridad
    Llamada > IVR > SMS. Sin toque efectivo en ventana ⇒ Espontáneo (C4).
    """
    mejor: Touch | None = None
    for t in touches_de_la_dama:
        if not t.efectivo:  # C1
            continue
        if t.num_dama != payment.num_dama:
            continue
        delta = dif_dias(payment.fecha_pago, t.dia)
        if delta < 0 or delta > VENTANA_DIAS:
            continue
        if mejor is None:
            mejor = t
        elif t.dia > mejor.dia:
            mejor = t
        elif t.dia == mejor.dia and PRIORIDAD_CANAL[t.canal] > PRIORIDAD_CANAL[mejor.canal]:
            mejor = t

    if mejor is None:
        return "Espontaneo", None
    return mejor.canal, mejor


def attribute_all(
    payments: list[Payment], touches: list[Touch], fecha_corte_canal: str | None
) -> list[Attribution]:
    """Atribuye TODOS los pagos (modelo primario) y marca sesgo temporal por pago."""
    por_dama: dict[int, list[Touch]] = {}
    for t in touches:
        if not t.efectivo:  # C1: solo efectivos entran al índice
            continue
        por_dama.setdefault(t.num_dama, []).append(t)

    out: list[Attribution] = []
    for p in payments:
        candidatos = por_dama.get(p.num_dama, [])
        canal, touch = attribute_last_touch(p, candidatos)
        fuera = fecha_corte_canal is not None and dif_dias(p.fecha_pago, fecha_corte_canal) > 0
        out.append(Attribution(payment=p, canal=canal, touch=touch, fuera_de_ventana=fuera))
    return out


def resumen_primario(atribs: list[Attribution]) -> list[dict[str, Any]]:
    """Agrega el resultado del modelo primario por canal."""
    acc: dict[str, dict[str, Any]] = {}
    total = 0.0
    for a in atribs:
        r = a.payment.recuperado
        total += r
        cur = acc.setdefault(a.canal, {"monto": 0.0, "pagos": 0, "damas": set()})
        cur["monto"] += r
        cur["pagos"] += 1
        cur["damas"].add(a.payment.num_dama)

    orden = ["Llamada", "IVR", "SMS", "Espontaneo"]
    res = []
    for c in orden:
        if c not in acc:
            continue
        cur = acc[c]
        res.append(
            {
                "canal": c,
                "monto": cur["monto"],
                "pagos": cur["pagos"],
                "consultoras": len(cur["damas"]),
                "pct": cur["monto"] / total if total > 0 else 0.0,
            }
        )
    return res


def influence_model(payments: list[Payment], touches: list[Touch]) -> dict[str, Any]:
    """MODELO SECUNDARIO — influencia (any-touch).

    % del monto de consultoras que recibieron ≥1 contacto efectivo de cada canal.
    Sin ventana. SUMA > 100% (una dama puede ser tocada por varios canales).
    """
    canales_por_dama: dict[int, set[str]] = {}
    for t in touches:
        if not t.efectivo:  # C1
            continue
        canales_por_dama.setdefault(t.num_dama, set()).add(t.canal)

    acc = {c: {"monto": 0.0, "damas": set()} for c in CANALES_REALES}
    total = 0.0
    for p in payments:
        total += p.recuperado
        canales = canales_por_dama.get(p.num_dama)
        if not canales:
            continue
        for c in canales:
            acc[c]["monto"] += p.recuperado
            acc[c]["damas"].add(p.num_dama)

    canales = [
        {
            "canal": c,
            "monto": acc[c]["monto"],
            "consultoras": len(acc[c]["damas"]),
            "pct": acc[c]["monto"] / total if total > 0 else 0.0,
        }
        for c in CANALES_REALES
    ]
    return {"canales": canales, "total": total}


def sesgo_temporal(payments: list[Payment], fecha_corte_canal: str | None) -> dict[str, Any]:
    """SESGO TEMPORAL (§4) — pagos posteriores al corte de datos de canal.

    No pueden recibir atribución; entran como espontáneo por construcción. Se
    reporta como alerta metodológica, no como hallazgo de negocio.
    """
    monto_total = 0.0
    monto_fuera = 0.0
    pagos_fuera = 0
    for p in payments:
        monto_total += p.recuperado
        if fecha_corte_canal is not None and dif_dias(p.fecha_pago, fecha_corte_canal) > 0:
            monto_fuera += p.recuperado
            pagos_fuera += 1
    return {
        "fecha_corte_canal": fecha_corte_canal,
        "monto_fuera_de_ventana": monto_fuera,
        "monto_total": monto_total,
        "pct_fuera_de_ventana": monto_fuera / monto_total if monto_total > 0 else 0.0,
        "pagos_fuera_de_ventana": pagos_fuera,
    }


def eficiencia_por_toque(atribs: list[Attribution], touches: list[Touch]) -> dict[str, float]:
    """Eficiencia por toque = monto atribuido al canal ÷ nº de toques efectivos."""
    monto = {c: 0.0 for c in CANALES_REALES}
    for a in atribs:
        if a.canal in monto:
            monto[a.canal] += a.payment.recuperado
    toques = {c: 0 for c in CANALES_REALES}
    for t in touches:
        if t.efectivo:
            toques[t.canal] += 1
    return {c: (monto[c] / toques[c] if toques[c] > 0 else 0.0) for c in CANALES_REALES}
