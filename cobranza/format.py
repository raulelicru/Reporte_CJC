"""Formateadores de cifras. Toda cifra usa tabular-nums en la UI (§9)."""
from __future__ import annotations

from datetime import date


def money(n: float | None) -> str:
    v = n or 0
    return f"${v:,.0f}"


def money_k(n: float | None) -> str:
    v = n or 0
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:.0f}k"
    return money(v)


def pct(n: float | None, digits: int = 1) -> str:
    return f"{(n or 0) * 100:.{digits}f}%"


def num(n: float | None) -> str:
    return f"{(n or 0):,.0f}"


def dias_entre(desde: str | None, hasta: str | None) -> int | None:
    if not desde or not hasta:
        return None
    try:
        return (date.fromisoformat(hasta[:10]) - date.fromisoformat(desde[:10])).days
    except ValueError:
        return None


def delta(actual: float, previo: float | None):
    if previo is None or previo == 0:
        return {"texto": "—", "signo": "flat"}
    d = (actual - previo) / abs(previo)
    signo = "up" if d > 0.001 else "down" if d < -0.001 else "flat"
    return {"texto": f"{'+' if d > 0 else ''}{d * 100:.1f}%", "signo": signo}
