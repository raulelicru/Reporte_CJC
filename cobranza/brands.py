"""Configuración por marca (multi-tenant).

Arabela y Natura entregan archivos distintos y hablan distinto (Arabela: 'dama',
temporalidades Inactiva/MNI/Mora 1-3/IM; Natura: 'consultora'). Toda la parte
específica de marca vive AQUÍ: terminología, orden de temporalidades, alias de
columnas para la ingesta y moneda. El resto de la app es idéntico para ambas.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Brand:
    id: str
    nombre: str
    unidad: str            # singular minúscula: "dama" / "consultora"
    unidad_plural: str     # "damas" / "consultoras"
    unidad_cap: str        # "Dama" / "Consultora"
    moneda: str = "MXN"
    # Orden de severidad de temporalidad (índice = rank; mayor = más severo).
    temporalidades: tuple[str, ...] = ()
    # Alias EXTRA de columnas por archivo/campo (extienden los candidatos base
    # del parser). Clave: archivo → campo → [candidatos]. Vacío = usa los base.
    aliases: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def unit(self, n: int = 1) -> str:
        return self.unidad if n == 1 else self.unidad_plural


ARABELA = Brand(
    id="arabela",
    nombre="Arabela",
    unidad="dama",
    unidad_plural="damas",
    unidad_cap="Dama",
    moneda="MXN",
    # Del prompt: [Inactiva, MNI, Mora 1, Mora 2, Mora 3, IM] (IM = más severo).
    temporalidades=("Inactiva", "MNI", "Mora 1", "Mora 2", "Mora 3", "IM"),
    aliases={
        "cartera": {"num_dama": ["NumDama", "No. Dama"], "dama_deuda": ["Dama-deuda"]},
        "gestiones": {"num_dama": ["CODIGO", "No. Dama"], "gestor": ["NOMBRE", "NOMBRE GESTOR"]},
        "ivr": {"num_dama": ["No. Dama", "Nodama"], "fecha": ["call_date", "Fecha de la Llamada"]},
        "vicidial": {"num_dama": ["No. De Dama", "No. Dama"]},
        "sms": {"num_dama": ["Dama", "No. Dama"]},
    },
)

NATURA = Brand(
    id="natura",
    nombre="Natura",
    unidad="consultora",
    unidad_plural="consultoras",
    unidad_cap="Consultora",
    moneda="MXN",
    # Placeholder: se ajusta cuando lleguen los archivos reales de Natura.
    temporalidades=("Al corriente", "Mora 1", "Mora 2", "Mora 3", "Castigo"),
    aliases={
        # Natura suele nombrar el código como 'Consultora'/'Cod Consultora'.
        "cartera": {"num_dama": ["Consultora", "CodConsultora", "Cod Consultora", "NumConsultora"]},
        "gestiones": {"num_dama": ["Consultora", "CODIGO", "CodConsultora"], "gestor": ["NOMBRE", "NOMBRE GESTOR"]},
        "ivr": {"num_dama": ["Consultora", "No. Consultora", "call_date"]},
        "sms": {"num_dama": ["Consultora", "Dama"]},
    },
)

BRANDS: dict[str, Brand] = {ARABELA.id: ARABELA, NATURA.id: NATURA}
DEFAULT_BRAND = ARABELA


def get_brand(brand_id: str | None) -> Brand:
    return BRANDS.get((brand_id or "").lower(), DEFAULT_BRAND)


def temp_rank(brand: Brand, temp: str | None) -> int:
    """Rank de severidad de una temporalidad (−1 si no está en el orden)."""
    if not temp:
        return -1
    norm = temp.strip().lower()
    for i, t in enumerate(brand.temporalidades):
        if t.lower() == norm:
            return i
    return -1
