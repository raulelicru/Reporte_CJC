"""Ingesta de los 6 .xlsx (§3) → dataset normalizado + perfilado.

Los tratamos como CRUDOS, no como verdad limpia. Aplica las reglas
estructurales de §4 en el punto de construcción:
  C1 · marca `efectivo` en cada toque con el predicado de su fuente.
  C2 · gestiones + vicidial = un canal; los toques de Llamada salen del CRM,
       Vicidial solo aporta roster de agentes y costo del marcador.
  C3 · el marcador automático se contabiliza como costo, jamás como toque.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

_PROMESA_DM = re.compile(r"^(\d{1,2})\s*/\s*(\d{1,2})(?:\s*/\s*(\d{2,4}))?$")


def _parse_promesa(val, fecha_hint: str | None) -> str | None:
    """Parsea PROMESA. Soporta 'dd/mm/yyyy' y el real 'd/m' (sin año): toma el
    año de la fecha de la gestión (fecha_hint ISO)."""
    if val is None or val == "":
        return None
    s = str(val).strip()
    m = _PROMESA_DM.match(s)
    if m:
        d, mo, y = m.groups()
        if y:
            year = int(y) + (2000 if len(y) == 2 else 0)
        elif fecha_hint:
            year = int(fecha_hint[:4])
        else:
            return None
        try:
            return date(year, int(mo), int(d)).isoformat()
        except ValueError:
            return None
    return to_iso_date(val)

from .coerce import (
    norm_key,
    tiene_encoding_roto,
    to_int,
    to_iso_date,
    to_num,
    to_str,
)
from .normalize import is_auto_dialer, normalize_name
from .predicates import gestion_efectiva, ivr_efectivo, sms_efectivo


@dataclass
class IngestResult:
    cartera: list[dict] = field(default_factory=list)
    pagos: list[dict] = field(default_factory=list)
    toques: list[dict] = field(default_factory=list)
    agentes: list[dict] = field(default_factory=list)
    gestiones: list[dict] = field(default_factory=list)
    profile: dict = field(default_factory=dict)
    flags: list[dict] = field(default_factory=list)
    header: dict = field(default_factory=dict)


def read_sheet(source) -> pd.DataFrame:
    """Lee la primera hoja de un .xlsx (ruta o buffer) a DataFrame."""
    return pd.read_excel(source, sheet_name=0, engine="openpyxl")


def _colmap(df: pd.DataFrame, mapping: dict[str, list[str]]) -> dict[str, str | None]:
    """Resuelve columnas por candidatos (case/acento-insensible)."""
    norm_to_actual = {norm_key(c): c for c in df.columns}
    out: dict[str, str | None] = {}
    for canon, cands in mapping.items():
        out[canon] = next((norm_to_actual[norm_key(c)] for c in cands if norm_key(c) in norm_to_actual), None)
    return out


def _records(df: pd.DataFrame, cm: dict[str, str | None]) -> list[dict]:
    """Extrae solo las columnas resueltas, renombradas a canónicas, como dicts."""
    cols = {actual: canon for canon, actual in cm.items() if actual is not None}
    sub = df[list(cols.keys())].rename(columns=cols)
    return sub.to_dict("records")


def _flag(flags, tipo, detalle, severidad="info"):
    flags.append({"tipo": tipo, "detalle": detalle, "severidad": severidad})


def _max_iso(a, b):
    if not a:
        return b
    if not b:
        return a
    return a if a > b else b


def _min_iso(a, b):
    if not a:
        return b
    if not b:
        return a
    return a if a < b else b


def build_ingest(sheets: dict[str, pd.DataFrame]) -> IngestResult:
    """sheets = {cartera, pagos, gestiones, vicidial, ivr, sms} DataFrames."""
    flags: list[dict] = []

    # ── 1) Cartera (dedup por Dama-deuda, última FechaEntrega) ──
    df = sheets["cartera"]
    cm = _colmap(df, {
        "num_dama": ["NumDama"], "anio": ["AnioCampaniaSaldo"],
        "dama_deuda": ["Dama-deuda", "DamaDeuda", "Dama_deuda"],
        "saldo_cobro": ["SaldoCobro"], "zona": ["NumeroZonaFacturacion", "zona"],
        "ruta": ["Ruta"], "fecha_entrega": ["FechaEntrega"],
    })
    cartera_by_key: dict[str, dict] = {}
    sin_llave = enc_roto = 0
    total_cartera = 0
    for row in _records(df, cm):
        total_cartera += 1
        num_dama = to_int(row.get("num_dama"))
        anio = to_str(row.get("anio"))
        dama = to_str(row.get("dama_deuda")) or (f"{num_dama}-{anio}" if num_dama is not None and anio else None)
        if num_dama is None or not dama:
            sin_llave += 1
            continue
        zona, ruta = to_str(row.get("zona")), to_str(row.get("ruta"))
        if tiene_encoding_roto(zona) or tiene_encoding_roto(ruta):
            enc_roto += 1
        fe = to_iso_date(row.get("fecha_entrega"))
        rec = {"dama_deuda": dama, "num_dama": num_dama, "saldo_cobro": to_num(row.get("saldo_cobro")),
               "zona": zona, "ruta": ruta, "fecha_entrega": fe}
        prev = cartera_by_key.get(dama)
        if prev is None or (fe or "") > (prev["fecha_entrega"] or ""):
            cartera_by_key[dama] = rec
    cartera = list(cartera_by_key.values())
    cartera_keys = set(cartera_by_key.keys())
    cartera_damas = {c["num_dama"] for c in cartera}
    saldo_by_key = {c["dama_deuda"]: c["saldo_cobro"] for c in cartera}

    dupes = total_cartera - len(cartera) - sin_llave
    if dupes > 0:
        _flag(flags, "cartera_duplicados", f"{dupes} Dama-deuda duplicadas deduplicadas por última FechaEntrega.")
    if sin_llave > 0:
        _flag(flags, "cartera_sin_llave", f"{sin_llave} filas sin NumDama/Dama-deuda descartadas.", "warn")
    if enc_roto > 0:
        _flag(flags, "encoding_roto", f"{enc_roto} filas de Cartera con encoding roto (Ã³/Ã±) en zona/ruta.", "warn")

    # ── 2) Pagos (filtrados a cartera + recuperado) ──
    df = sheets["pagos"]
    cm = _colmap(df, {
        "num_dama": ["NumDama"], "anio": ["AnioCampaniaSaldo"],
        "dama_deuda": ["Dama-deuda", "DamaDeuda"], "id_cobrador": ["IdCobrador"],
        "fecha_pago": ["FechaEntrega", "FechaPago"], "saldo_remanente": ["SaldoCampania", "SaldoRemanente"],
        "estado_proceso": ["EstadoProceso"],
    })
    pagos_by_key: dict[str, dict] = {}
    fuera_cartera = 0
    for row in _records(df, cm):
        num_dama = to_int(row.get("num_dama"))
        anio = to_str(row.get("anio"))
        dama = to_str(row.get("dama_deuda")) or (f"{num_dama}-{anio}" if num_dama is not None and anio else None)
        if num_dama is None or not dama:
            continue
        if dama not in cartera_keys:  # filtra campañas anteriores (ej. C11)
            fuera_cartera += 1
            continue
        fp = to_iso_date(row.get("fecha_pago"))
        rem = to_num(row.get("saldo_remanente"))
        rec = {"dama_deuda": dama, "num_dama": num_dama, "id_cobrador": to_str(row.get("id_cobrador")),
               "fecha_pago": fp, "saldo_remanente": rem, "estado_proceso": to_str(row.get("estado_proceso")),
               "recuperado": max(0.0, saldo_by_key.get(dama, 0.0) - rem)}
        prev = pagos_by_key.get(dama)
        if prev is None or (fp or "") >= (prev["fecha_pago"] or ""):
            pagos_by_key[dama] = rec
    pagos = list(pagos_by_key.values())
    if fuera_cartera > 0:
        _flag(flags, "pagos_fuera_de_cartera", f"{fuera_cartera} pagos de campañas anteriores (fuera de la Cartera cargada) filtrados.")

    # ── 3) Gestiones (CRM) ──
    df = sheets["gestiones"]
    cm = _colmap(df, {
        "num_dama": ["CODIGO", "NumDama"], "gestor": ["NOMBRE GESTOR", "NOMBRE"], "fecha": ["FECHA"],
        "tipo_gestion": ["TIPO DE GESTION"], "tipificacion": ["TIPIFICACION", "TIPIFICACIlON"],
        "promesa": ["PROMESA", "DIA PROM"], "medicion": ["MEDICION"], "temp": ["temp"],
    })
    gestiones: list[dict] = []
    medicion_vacia = sin_fecha = sistema = 0
    for row in _records(df, cm):
        num_dama = to_int(row.get("num_dama"))
        if num_dama is None:
            continue
        fecha = to_iso_date(row.get("fecha"))
        if not fecha:
            sin_fecha += 1
        if not to_str(row.get("medicion")):
            medicion_vacia += 1
        gestor = to_str(row.get("gestor"))
        norm = normalize_name(gestor) if gestor else None
        # "Sistema" y nombres del marcador (Outbound Auto Dial / Inbound No Agent)
        # son entradas automáticas, no gestores humanos (C2/C3).
        if norm in ("sistema", "") or is_auto_dialer(gestor):
            if norm:
                sistema += 1
            norm = None
        gestiones.append({
            "num_dama": num_dama, "agente_norm": norm,
            "agente_display": gestor, "fecha": fecha, "tipo_gestion": to_str(row.get("tipo_gestion")),
            "tipificacion": to_str(row.get("tipificacion")),
            "promesa_fecha": _parse_promesa(row.get("promesa"), fecha),
            "monto_prometido": None, "temp": to_str(row.get("temp")),
        })
    if sistema > 0:
        _flag(flags, "gestiones_sistema", f"{sistema} gestiones automáticas ('Sistema') excluidas del roster de gestores (no son personas).")
    n_gest = len(gestiones)
    if medicion_vacia > 0:
        _pct = medicion_vacia / max(1, n_gest) * 100
        _flag(flags, "medicion_vacia", f"MEDICION vacía en {medicion_vacia}/{n_gest} filas ({_pct:.1f}%) — inutilizable, no se muestra.")
    if sin_fecha > 0:
        _flag(flags, "gestiones_sin_fecha", f"{sin_fecha} gestiones sin FECHA parseable.", "warn")

    # ── 4) Vicidial → roster + costo del marcador (C3) ──
    df = sheets["vicidial"]
    cm = _colmap(df, {
        "full_name": ["full_name"], "length_in_sec": ["length_in_sec"], "status_name": ["status_name", "status"],
    })
    agentes_vici: dict[str, str] = {}
    costo = {"llamadas": 0, "minutos": 0.0, "contactos_efectivos": 0}
    for row in _records(df, cm):
        full = to_str(row.get("full_name"))
        if is_auto_dialer(full):
            costo["llamadas"] += 1
            costo["minutos"] += to_num(row.get("length_in_sec")) / 60.0
            continue
        if full:
            agentes_vici[normalize_name(full)] = full

    agentes_crm = {g["agente_norm"]: g["agente_display"] for g in gestiones if g["agente_norm"]}
    solo_crm, solo_vici = [], []
    agentes: list[dict] = []
    for norm in set(agentes_crm) | set(agentes_vici):
        if not norm:
            continue
        en_crm, en_vici = norm in agentes_crm, norm in agentes_vici
        fuentes = (["crm"] if en_crm else []) + (["vicidial"] if en_vici else [])
        if en_crm and not en_vici:
            solo_crm.append(agentes_crm[norm])
        if en_vici and not en_crm:
            solo_vici.append(agentes_vici[norm])
        agentes.append({"nombre_norm": norm, "nombre_display": agentes_crm.get(norm) or agentes_vici.get(norm), "fuentes": fuentes})
    if solo_crm or solo_vici:
        _flag(flags, "roster_divergente", f"Agentes solo en CRM: {len(solo_crm)}; solo en Vicidial: {len(solo_vici)}. Revisar match de nombres (C2).")

    # ── 5) Toques unificados ──
    toques: list[dict] = []
    for g in gestiones:  # Llamada ← CRM humano (trae el resultado). C1.
        # Solo gestiones de un gestor real (no 'Sistema') son toques de Llamada.
        if not g["fecha"] or not g["agente_norm"]:
            continue
        toques.append({"num_dama": g["num_dama"], "canal": "Llamada", "dia": g["fecha"],
                       "efectivo": gestion_efectiva(g["tipo_gestion"]), "meta": {"agente": g["agente_norm"]}})

    # IVR/Reminder: el export real viene en esquema Vicidial (call_date, No. Dama,
    # status_name). Se aceptan ambos formatos (spec y real).
    df = sheets["ivr"]
    cm = _colmap(df, {
        "num_dama": ["Nodama", "No. Dama", "No Dama", "NoDama", "NumDama"],
        "fecha": ["Fecha de la Llamada", "call_date"],
        # Preferir la columna DESCRIPTIVA (status_name / Estado) sobre el código
        # terse (status = AB/AA/DROP), que no dice si conectó.
        "status": ["status_name", "Estado de la Llamada", "Estado Final", "Status"],
        "dtmf": ["Respuesta DTMF"],
    })
    ivr_sin_fecha = ivr_total = 0
    ivr_en_cartera = 0
    for row in _records(df, cm):
        ivr_total += 1
        num_dama = to_int(row.get("num_dama"))
        fecha = to_iso_date(row.get("fecha"))
        if not fecha:
            ivr_sin_fecha += 1
            continue
        if num_dama is None:
            continue
        if num_dama in cartera_damas:
            ivr_en_cartera += 1
        toques.append({"num_dama": num_dama, "canal": "IVR", "dia": fecha,
                       "efectivo": ivr_efectivo(to_str(row.get("status"))), "meta": {"dtmf": to_str(row.get("dtmf"))}})
    if ivr_sin_fecha > 0:
        _flag(flags, "ivr_sin_fecha", f"{ivr_sin_fecha} llamadas IVR sin fecha parseable — excluidas de atribución, contadas aparte.", "warn")

    df = sheets["sms"]
    cm = _colmap(df, {"num_dama": ["Dama"], "fecha": ["Fecha Envio"], "descripcion": ["Descripcion"], "operador": ["Operador"]})
    sms_dama_nula = sms_total = sms_en_cartera = 0
    for row in _records(df, cm):
        sms_total += 1
        num_dama = to_int(row.get("num_dama"))
        if num_dama is None:
            sms_dama_nula += 1
            continue
        fecha = to_iso_date(row.get("fecha"))
        if not fecha:
            continue
        if num_dama in cartera_damas:
            sms_en_cartera += 1
        toques.append({"num_dama": num_dama, "canal": "SMS", "dia": fecha,
                       "efectivo": sms_efectivo(to_str(row.get("descripcion"))), "meta": {"operador": to_str(row.get("operador"))}})
    if sms_dama_nula > 0:
        _flag(flags, "sms_dama_nula", f"{sms_dama_nula} SMS con Dama no coercible a entero — descartados.")

    # ── 6) Fechas de corte / madurez ──
    fecha_corte = None
    for t in toques:
        fecha_corte = _max_iso(fecha_corte, t["dia"])
    fecha_liberacion = None
    for c in cartera:
        fecha_liberacion = _min_iso(fecha_liberacion, c["fecha_entrega"])
    fecha_max_pago = None
    for p in pagos:
        fecha_max_pago = _max_iso(fecha_max_pago, p["fecha_pago"])

    # ── 7) Perfilado ──
    gest_en_cartera = sum(1 for g in gestiones if g["num_dama"] in cartera_damas)
    profile = {
        "filas": {"cartera": len(cartera), "pagos": len(pagos), "gestiones": n_gest,
                  "vicidial": costo["llamadas"] + len(agentes_vici), "ivr": ivr_total, "sms": sms_total, "toques": len(toques)},
        "cruces": {"pagos_en_cartera": 1.0,
                   "gestiones_en_cartera": gest_en_cartera / n_gest if n_gest else 0.0,
                   "ivr_en_cartera": ivr_en_cartera / ivr_total if ivr_total else 0.0,
                   "sms_en_cartera": sms_en_cartera / sms_total if sms_total else 0.0},
        "fecha_corte_datos": fecha_corte, "fecha_liberacion": fecha_liberacion, "fecha_max_pago": fecha_max_pago,
        "costo_marcador": costo, "agentes_solo_crm": solo_crm, "agentes_solo_vicidial": solo_vici,
    }
    if fecha_max_pago and fecha_corte and fecha_max_pago > fecha_corte:
        _flag(flags, "sesgo_temporal", f"Pagos hasta {fecha_max_pago} vs. datos de canal hasta {fecha_corte}: el tramo posterior entra como espontáneo por construcción.", "warn")

    return IngestResult(
        cartera=cartera, pagos=pagos, toques=toques, agentes=agentes, gestiones=gestiones,
        profile=profile, flags=flags,
        header={"saldo_asignado": sum(c["saldo_cobro"] for c in cartera), "deudas": len(cartera), "consultoras": len(cartera_damas)},
    )
