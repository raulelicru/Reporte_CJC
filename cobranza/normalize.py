"""Normalización de nombres de agente (C2).

Los ~21 gestores del CRM coinciden con los agentes de Vicidial por nombre
normalizado: minúsculas, sin acentos, sin dobles espacios, trim.
"""
from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_SPACES = re.compile(r"\s+")


def normalize_name(raw: str | None) -> str:
    if not raw:
        return ""
    s = unicodedata.normalize("NFD", str(raw))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # quita diacríticos
    s = s.lower()
    s = _NON_ALNUM.sub(" ", s)
    s = _SPACES.sub(" ", s)
    return s.strip()


# Marcador automático de Vicidial (C3): costo de telefonía, no canal.
_MARCADOR = {normalize_name("Outbound Auto Dial"), normalize_name("Inbound No Agent")}


def is_auto_dialer(full_name: str | None) -> bool:
    return normalize_name(full_name) in _MARCADOR
