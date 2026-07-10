"""Coacciones y parseo de fechas para la ingesta (§3).

Cada trampa documentada se maneja como REGLA, no como bug.
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime, timedelta

import pandas as pd

_MOJIBAKE = re.compile(r"Ã.|Â.|â€")
_DDMMYYYY = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})")
_EXCEL_EPOCH = date(1899, 12, 30)


def to_iso_date(value) -> str | None:
    """Convierte a ISO YYYY-MM-DD o None si no es parseable."""
    if value is None or (isinstance(value, float) and math.isnan(value)) or value == "":
        return None

    # pandas Timestamp / datetime / date
    if isinstance(value, (pd.Timestamp, datetime, date)):
        try:
            return pd.Timestamp(value).date().isoformat()
        except Exception:
            return None

    # entero/float YYYYMMDD (FechaEntrega)
    if isinstance(value, (int, float)) and float(value).is_integer():
        iv = int(value)
        if iv > 19000101:
            return _from_yyyymmdd(str(iv))
        # serial de Excel
        if 20000 < iv < 60000:
            return (_EXCEL_EPOCH + timedelta(days=iv)).isoformat()

    s = str(value).strip()
    if re.fullmatch(r"\d{8}", s):
        return _from_yyyymmdd(s)

    m = _DDMMYYYY.match(s)
    if m:
        d, mo, y = m.groups()
        try:
            return date(int(y), int(mo), int(d)).isoformat()
        except ValueError:
            return None

    try:
        return pd.to_datetime(s, dayfirst=False, errors="raise").date().isoformat()
    except Exception:
        return None


def _from_yyyymmdd(s: str) -> str | None:
    if not re.fullmatch(r"\d{8}", s):
        return None
    y, mo, d = int(s[:4]), int(s[4:6]), int(s[6:8])
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def to_int(value) -> int | None:
    """Coacciona a entero; None si vacío o no numérico (SMS Dama puede venir texto)."""
    if value is None or value == "":
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (int, float)):
        return int(value) if math.isfinite(value) else None
    digits = re.sub(r"[^\d-]", "", str(value))
    if digits in ("", "-"):
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def to_num(value) -> float:
    """Coacciona a decimal; 0.0 por defecto."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, float) and math.isnan(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else 0.0
    cleaned = re.sub(r"[^\d.,-]", "", str(value)).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def to_str(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    s = str(value).strip()
    return s or None


def tiene_encoding_roto(value) -> bool:
    """Detecta mojibake (Ã³/Ã±/Â) — se reporta como hallazgo, no se esconde."""
    return isinstance(value, str) and bool(_MOJIBAKE.search(value))


def norm_key(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s.lower())
