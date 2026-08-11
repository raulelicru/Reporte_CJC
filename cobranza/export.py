"""Exportes descargables (.xlsx) — sin dependencias externas más allá de openpyxl."""
from __future__ import annotations

import io


def cartera_nueva_xlsx(cartera_nueva: dict, brand, campaign: dict) -> bytes:
    """Genera la NUEVA cartera (no tocada y sin pago) como .xlsx en memoria.

    Columnas listas para re-subir como una nueva campaña o entregar a la
    operación. Devuelve los bytes del archivo.
    """
    import pandas as pd

    filas = (cartera_nueva or {}).get("filas") or []
    unidad = brand.unidad_cap
    df = pd.DataFrame([{
        f"Num{unidad}": f.get("num_dama"),
        f"{unidad}-deuda": f.get("dama_deuda"),
        "SaldoCobro": f.get("saldo"),
        "Zona": f.get("zona"),
        "Ruta": f.get("ruta"),
        "Temporalidad": f.get("temporalidad"),
    } for f in filas])
    if df.empty:  # asegura encabezados aunque no haya filas
        df = pd.DataFrame(columns=[f"Num{unidad}", f"{unidad}-deuda", "SaldoCobro", "Zona", "Ruta", "Temporalidad"])

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        df.to_excel(xl, index=False, sheet_name="Nueva cartera")
    return buf.getvalue()


def cartera_nueva_filename(brand, campaign: dict) -> str:
    anio = campaign.get("anio_campania", "")
    snap = campaign.get("fecha_snapshot", "")
    return f"nueva_cartera_{brand.id}_{anio}_{snap}.xlsx".replace(" ", "")
