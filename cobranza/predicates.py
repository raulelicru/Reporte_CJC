"""Predicados de contacto efectivo (C1) por fuente y estado de liquidación.

C1 · Contacto efectivo ≠ intento — un marcado que no conecta jamás atribuye.
Puros y testeables; la ingesta los usa para marcar `Touch.efectivo`.
"""
from __future__ import annotations

import unicodedata


def _norm(s: str | None) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().strip()


def gestion_efectiva(tipo_gestion: str | None) -> bool:
    """Gestiones (CRM) → efectivo si TIPO DE GESTION == 'CONTACTO'."""
    return _norm(tipo_gestion) == "contacto"


# Estados del blaster IVR (Vicidial) que NO son contacto con una persona.
_IVR_NO_CONTACTO = (
    "ocupado", "buzon", "no answer", "noanswer", "no contesta",
    "no disponible", "drop", "pre-routing", "prerouting", "pre routing",
)


def ivr_efectivo(status: str | None) -> bool:
    """IVR/Reminder → efectivo si la llamada conectó con una persona.

    Soporta el formato del spec (Status == 'Contacto') y el real (Vicidial
    `status_name`: 'Ocupado automatico', 'Buzon automatico', 'Llamada
    transferida', 'PROMESA DE PAGO', …). Efectivo = hay estado y no es un
    no-contacto automático (ocupado, buzón, no contesta, drop, sin agente…).
    """
    n = _norm(status)
    if not n:
        return False
    if n == "contacto":
        return True
    return not any(k in n for k in _IVR_NO_CONTACTO)


def sms_efectivo(descripcion: str | None) -> bool:
    """SMS → efectivo si Descripcion ∈ {Exitoso, Enviado}."""
    d = _norm(descripcion)
    return d in ("exitoso", "enviado")


def es_liquidacion(estado_proceso: str | None) -> bool:
    """R y E ⇒ saldo remanente 0 = liquidado (catálogo abierto)."""
    return _norm(estado_proceso) in ("r", "e")
