"""Capa de datos sobre Neon (Postgres puro) con psycopg.

Sin Auth/RLS de Supabase: el login vive en la tabla `usuarios` (contraseña con
hash bcrypt) y el aislamiento por organización se aplica en la app. La conexión
usa DATABASE_URL (cadena de conexión de Neon). Persistir una campaña es
idempotente por (org, anio_campania, fecha_snapshot): un snapshot por día.
"""
from __future__ import annotations

import os
from datetime import date as _date
from typing import Any

import bcrypt
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

try:  # st.secrets es opcional (permite correr fuera de Streamlit)
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

DEFAULT_ORG = "00000000-0000-0000-0000-000000000001"


def _cfg(key: str) -> str | None:
    if st is not None:
        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass
    return os.environ.get(key)


def _dsn() -> str | None:
    return _cfg("DATABASE_URL")


def is_configured() -> bool:
    return bool(_dsn())


def _conn() -> psycopg.Connection:
    dsn = _dsn()
    if not dsn:
        raise RuntimeError("Falta DATABASE_URL (cadena de conexión de Neon). Ver .env.example.")
    return psycopg.connect(dsn, row_factory=dict_row)


def _q(sql: str, params: tuple = (), fetch: str = "all") -> Any:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if fetch == "all":
            return cur.fetchall()
        if fetch == "one":
            return cur.fetchone()
        return None


# ── Auth (tabla usuarios, bcrypt) ──────────────────────────────────────────
def count_users() -> int:
    row = _q("select count(*) as n from usuarios", fetch="one")
    return int(row["n"]) if row else 0


def create_user(email: str, password: str, rol: str = "admin",
                nombre: str | None = None, org_id: str = DEFAULT_ORG) -> dict:
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return _q(
        """insert into usuarios (email, password_hash, rol, org_id, nombre)
           values (%s, %s, %s, %s, %s)
           on conflict (email) do update set password_hash = excluded.password_hash
           returning id, email, rol, org_id, nombre""",
        (email.strip().lower(), pw_hash, rol, org_id, nombre or email),
        fetch="one",
    )


def sign_in(email: str, password: str) -> dict | None:
    row = _q("select id, email, password_hash, rol, org_id, nombre from usuarios where email = %s",
             (email.strip().lower(),), fetch="one")
    if not row:
        return None
    ph = row["password_hash"]
    ph = ph if isinstance(ph, bytes) else ph.encode()
    if not bcrypt.checkpw(password.encode(), ph):
        return None
    return {"id": str(row["id"]), "email": row["email"], "rol": row["rol"],
            "org_id": str(row["org_id"]), "nombre": row["nombre"]}


def get_profile(user_id: str) -> dict | None:
    row = _q("select id as user_id, rol, org_id, nombre, equipo from usuarios where id = %s",
             (user_id,), fetch="one")
    if row:
        row["org_id"] = str(row["org_id"])
        row["user_id"] = str(row["user_id"])
    return row


# ── Lecturas ────────────────────────────────────────────────────────────────
def get_campaigns() -> list[dict]:
    rows = _q("""select id, org_id, anio_campania, nombre, fecha_snapshot, fecha_liberacion,
                        fecha_corte_datos, saldo_asignado, deudas, consultoras, created_at
                 from campaigns order by anio_campania desc, fecha_snapshot desc""")
    return [_stringify_dates(r) for r in rows]


def _rows(table: str, cid: str, order: str | None = None) -> list[dict]:
    sql = f"select * from {table} where campaign_id = %s" + (f" order by {order}" if order else "")
    return [_stringify_dates(r) for r in _q(sql, (cid,))]


def get_resumen(cid): return _one("metrics_resumen", cid)
def get_canal(cid): return _rows("metrics_canal", cid)
def get_temporalidad(cid): return _rows("metrics_temporalidad", cid)
def get_diaria(cid): return _rows("metrics_diaria", cid, order="fecha")
def get_secuencias(cid): return _rows("metrics_secuencia", cid)
def get_quality_flags(cid): return _rows("quality_flags", cid)
def get_costo_marcador(cid): return _one("costo_marcador", cid)


def _one(table: str, cid: str) -> dict | None:
    r = _q(f"select * from {table} where campaign_id = %s", (cid,), fetch="one")
    return _stringify_dates(r) if r else None


def get_agentes(cid: str) -> list[dict]:
    rows = _q("""select ma.*, a.nombre_display as nombre, m.nombre_display as mentor_nombre
                 from metrics_agente ma
                 left join agentes a on a.id = ma.agente_id
                 left join agentes m on m.id = ma.mentor_sugerido
                 where ma.campaign_id = %s""", (cid,))
    return [_stringify_dates(r) for r in rows]


def get_comparativa() -> dict:
    camps = [_stringify_dates(r) for r in _q(
        "select * from campaigns order by anio_campania, fecha_snapshot")]
    resumenes = [_stringify_dates(r) for r in _q("select * from metrics_resumen")]
    canales = _q("select * from metrics_canal")
    agentes = _q("select campaign_id, pdp, pdp_cumplidas from metrics_agente")
    cumpl: dict[str, dict] = {}
    for a in agentes:
        cur = cumpl.setdefault(str(a["campaign_id"]), {"pdp": 0, "cumpl": 0})
        cur["pdp"] += a["pdp"] or 0
        cur["cumpl"] += a["pdp_cumplidas"] or 0
    cumplimiento = {k: (v["cumpl"] / v["pdp"] if v["pdp"] else 0.0) for k, v in cumpl.items()}
    return {"campaigns": camps, "resumenes": resumenes,
            "canales": [_stringify_dates(c) for c in canales], "cumplimiento": cumplimiento}


def get_historia_gestores() -> dict:
    rows = _q("""select ma.tasa_contacto, ma.pct_cumplimiento, ma.clasificacion,
                        a.nombre_norm, a.nombre_display, c.anio_campania, c.fecha_snapshot
                 from metrics_agente ma
                 join agentes a on a.id = ma.agente_id
                 join campaigns c on c.id = ma.campaign_id""")
    hist: dict[str, dict] = {}
    for r in rows:
        norm = r["nombre_norm"]
        etiqueta = (r["fecha_snapshot"].isoformat() if r.get("fecha_snapshot") else None) or r["anio_campania"] or "?"
        entry = hist.setdefault(norm, {"display": r["nombre_display"] or norm, "puntos": []})
        entry["puntos"].append({"anio": etiqueta, "contacto": float(r["tasa_contacto"]),
                                "cumplimiento": float(r["pct_cumplimiento"]), "clasificacion": r["clasificacion"]})
    for e in hist.values():
        e["puntos"].sort(key=lambda x: x["anio"])
    return hist


# ── Persistencia idempotente (transacción única) ───────────────────────────
def persist_campaign(org_id: str, anio: str, nombre: str, cargado_por: str | None,
                     ingest, metrics: dict, fecha_snapshot: str | None = None) -> str:
    snapshot = fecha_snapshot or _date.today().isoformat()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """insert into campaigns (org_id, anio_campania, nombre, fecha_snapshot,
                   fecha_liberacion, fecha_corte_datos, saldo_asignado, deudas, consultoras, cargado_por)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (org_id, anio_campania, fecha_snapshot) do update set
                   nombre=excluded.nombre, fecha_liberacion=excluded.fecha_liberacion,
                   fecha_corte_datos=excluded.fecha_corte_datos, saldo_asignado=excluded.saldo_asignado,
                   deudas=excluded.deudas, consultoras=excluded.consultoras, cargado_por=excluded.cargado_por
               returning id""",
            (org_id, anio, nombre, snapshot, ingest.profile.get("fecha_liberacion"),
             ingest.profile.get("fecha_corte_datos"), ingest.header["saldo_asignado"],
             ingest.header["deudas"], ingest.header["consultoras"], cargado_por),
        )
        campaign_id = cur.fetchone()["id"]

        for t in ["cartera", "pagos", "toques", "gestiones", "agentes", "costo_marcador",
                  "metrics_canal", "metrics_agente", "metrics_temporalidad", "metrics_diaria",
                  "metrics_secuencia", "metrics_resumen", "quality_flags"]:
            cur.execute(f"delete from {t} where campaign_id = %s", (campaign_id,))

        # agentes → id
        agente_id: dict[str, str] = {}
        for a in ingest.agentes:
            cur.execute("""insert into agentes (campaign_id, nombre_norm, nombre_display, fuentes)
                           values (%s,%s,%s,%s) returning id, nombre_norm""",
                        (campaign_id, a["nombre_norm"], a["nombre_display"], a["fuentes"]))
            row = cur.fetchone()
            agente_id[row["nombre_norm"]] = row["id"]

        cur.executemany(
            """insert into cartera (campaign_id, dama_deuda, num_dama, saldo_cobro, zona, ruta, fecha_entrega)
               values (%s,%s,%s,%s,%s,%s,%s)""",
            [(campaign_id, c["dama_deuda"], c["num_dama"], c["saldo_cobro"], c["zona"], c["ruta"], c["fecha_entrega"])
             for c in ingest.cartera])

        cur.executemany(
            """insert into pagos (campaign_id, dama_deuda, num_dama, id_cobrador, fecha_pago,
                   saldo_remanente, estado_proceso, recuperado) values (%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(campaign_id, p["dama_deuda"], p["num_dama"], p["id_cobrador"], p["fecha_pago"],
              p["saldo_remanente"], p["estado_proceso"], p["recuperado"]) for p in ingest.pagos])

        cur.executemany(
            """insert into toques (campaign_id, num_dama, canal, dia, efectivo, meta)
               values (%s,%s,%s,%s,%s,%s)""",
            [(campaign_id, t["num_dama"], t["canal"], t["dia"], t["efectivo"], Jsonb(t["meta"]))
             for t in ingest.toques])

        # Solo gestiones de un gestor humano (las ~94% 'Sistema' no aportan a las
        # métricas —ya calculadas en memoria— ni las lee ninguna vista).
        cur.executemany(
            """insert into gestiones (campaign_id, agente_id, num_dama, fecha, tipo_gestion,
                   tipificacion, promesa_fecha, monto_prometido, temp) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(campaign_id, agente_id.get(g["agente_norm"]),
              g["num_dama"], g["fecha"], g["tipo_gestion"], g["tipificacion"], g["promesa_fecha"],
              g["monto_prometido"], g["temp"]) for g in ingest.gestiones if g["agente_norm"]])

        cm = ingest.profile["costo_marcador"]
        cur.execute("""insert into costo_marcador (campaign_id, llamadas, minutos, contactos_efectivos)
                       values (%s,%s,%s,%s)""",
                    (campaign_id, cm["llamadas"], cm["minutos"], cm["contactos_efectivos"]))

        cur.executemany(
            """insert into metrics_canal (campaign_id, canal, monto_ultimo_toque, pagos, consultoras,
                   pct, eficiencia_por_toque, influencia_monto, influencia_pct)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(campaign_id, m["canal"], m["monto_ultimo_toque"], m["pagos"], m["consultoras"],
              m["pct"], m["eficiencia_por_toque"], m["influencia_monto"], m["influencia_pct"])
             for m in metrics["canal"]])

        cur.executemany(
            """insert into metrics_agente (campaign_id, agente_id, gestiones, contactos_efectivos,
                   tasa_contacto, pdp, pdp_cumplidas, pct_cumplimiento, recuperado_atribuido, pagadoras,
                   clasificacion, percentil_contacto, percentil_cumplimiento, mentor_sugerido)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(campaign_id, agente_id.get(a["agente_id"]), a["gestiones"], a["contactos_efectivos"],
              a["tasa_contacto"], a["pdp"], a["pdp_cumplidas"], a["pct_cumplimiento"],
              a["recuperado_atribuido"], 0, a["clasificacion"], a["percentil_contacto"],
              a["percentil_cumplimiento"], agente_id.get(a["mentor_sugerido"]) if a["mentor_sugerido"] else None)
             for a in metrics["agentes"] if agente_id.get(a["agente_id"])])

        cur.executemany(
            """insert into metrics_temporalidad (campaign_id, temp, saldo, recuperado, tasa, deudas)
               values (%s,%s,%s,%s,%s,%s)""",
            [(campaign_id, t["temp"], t["saldo"], t["recuperado"], t["tasa"], t["deudas"])
             for t in metrics["temporalidad"]])

        cur.executemany(
            """insert into metrics_diaria (campaign_id, fecha, recuperado, pagos, sms_enviados, es_blast, fuera_ventana)
               values (%s,%s,%s,%s,%s,%s,%s)""",
            [(campaign_id, d["fecha"], d["recuperado"], d["pagos"], d["sms_enviados"], d["es_blast"], d["fuera_ventana"])
             for d in metrics["diaria"]])

        cur.executemany(
            """insert into metrics_secuencia (campaign_id, cadena, pagos, recuperado) values (%s,%s,%s,%s)""",
            [(campaign_id, s["cadena"], s["pagos"], s["recuperado"]) for s in metrics["secuencias"]])

        rr = metrics["resumen"]
        cur.execute(
            """insert into metrics_resumen (campaign_id, recuperado, saldo_asignado, pct_recuperado,
                   deudas_liquidadas, saldo_pendiente, pct_pagos_sin_contacto, pct_espontaneo,
                   pct_fuera_ventana, pct_cartera_no_contactada)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (campaign_id, rr["recuperado"], rr["saldo_asignado"], rr["pct_recuperado"],
             rr["deudas_liquidadas"], rr["saldo_pendiente"], rr["pct_pagos_sin_contacto"],
             rr["pct_espontaneo"], rr["pct_fuera_ventana"], rr["pct_cartera_no_contactada"]))

        cur.executemany(
            """insert into quality_flags (campaign_id, tipo, detalle, severidad) values (%s,%s,%s,%s)""",
            [(campaign_id, f["tipo"], f["detalle"], f["severidad"]) for f in ingest.flags])

        conn.commit()
    return str(campaign_id)


def _stringify_dates(row: dict | None) -> dict | None:
    """Convierte date/UUID/Decimal a tipos JSON-friendly para la UI."""
    if not row:
        return row
    from datetime import date, datetime
    from decimal import Decimal
    from uuid import UUID
    out = {}
    for k, v in row.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return out
