"""Capa de datos Supabase (§5, §7): auth, persistencia idempotente y lecturas.

- El login usa Supabase Auth (email+contraseña) sobre un cliente anon; ese
  mismo cliente aplica RLS en las lecturas con la identidad del usuario.
- La ingesta/recálculo usa el service-role client (bypassa RLS), solo servidor.
- Persistir una campaña REEMPLAZA sus filas (idempotencia por campaign_id).
"""
from __future__ import annotations

import os
from datetime import date as _date
from typing import Any

from supabase import Client, create_client

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


def is_configured() -> bool:
    return bool(_cfg("SUPABASE_URL") and _cfg("SUPABASE_ANON_KEY"))


def anon_client() -> Client:
    return create_client(_cfg("SUPABASE_URL"), _cfg("SUPABASE_ANON_KEY"))


def admin_client() -> Client:
    url, key = _cfg("SUPABASE_URL"), _cfg("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (ver .env.example).")
    return create_client(url, key)


# ── Auth ──
def sign_in(client: Client, email: str, password: str):
    return client.auth.sign_in_with_password({"email": email, "password": password})


def get_profile(client: Client, user_id: str) -> dict | None:
    res = client.table("profiles").select("user_id, rol, equipo, nombre, org_id").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None


# ── Lecturas (RLS aplica con el cliente autenticado) ──
def get_campaigns(client: Client) -> list[dict]:
    return (
        client.table("campaigns")
        .select("*")
        .order("anio_campania", desc=True)
        .order("fecha_snapshot", desc=True)
        .execute()
        .data
        or []
    )


def _rows(client: Client, table: str, campaign_id: str, order: str | None = None) -> list[dict]:
    q = client.table(table).select("*").eq("campaign_id", campaign_id)
    if order:
        q = q.order(order)
    return q.execute().data or []


def get_resumen(client, cid):
    d = client.table("metrics_resumen").select("*").eq("campaign_id", cid).execute().data
    return d[0] if d else None


def get_canal(client, cid):
    return _rows(client, "metrics_canal", cid)


def get_agentes(client, cid) -> list[dict]:
    d = client.table("metrics_agente").select(
        "*, agentes:agente_id(nombre_display), mentor:mentor_sugerido(nombre_display)"
    ).eq("campaign_id", cid).execute().data or []
    for a in d:
        a["nombre"] = (a.get("agentes") or {}).get("nombre_display")
        a["mentor_nombre"] = (a.get("mentor") or {}).get("nombre_display")
    return d


def get_temporalidad(client, cid):
    return _rows(client, "metrics_temporalidad", cid)


def get_diaria(client, cid):
    return _rows(client, "metrics_diaria", cid, order="fecha")


def get_secuencias(client, cid):
    return _rows(client, "metrics_secuencia", cid)


def get_quality_flags(client, cid):
    return _rows(client, "quality_flags", cid)


def get_costo_marcador(client, cid):
    d = client.table("costo_marcador").select("*").eq("campaign_id", cid).execute().data
    return d[0] if d else None


def get_comparativa(client) -> dict:
    camps = client.table("campaigns").select("*").order("anio_campania").order("fecha_snapshot").execute().data or []
    resumenes = client.table("metrics_resumen").select("*").execute().data or []
    canales = client.table("metrics_canal").select("*").execute().data or []
    agentes = client.table("metrics_agente").select("campaign_id, pdp, pdp_cumplidas").execute().data or []
    cumpl: dict[str, dict] = {}
    for a in agentes:
        cur = cumpl.setdefault(a["campaign_id"], {"pdp": 0, "cumpl": 0})
        cur["pdp"] += a["pdp"] or 0
        cur["cumpl"] += a["pdp_cumplidas"] or 0
    cumplimiento = {k: (v["cumpl"] / v["pdp"] if v["pdp"] else 0.0) for k, v in cumpl.items()}
    return {"campaigns": camps, "resumenes": resumenes, "canales": canales, "cumplimiento": cumplimiento}


def get_historia_gestores(client) -> dict:
    d = client.table("metrics_agente").select(
        "tasa_contacto, pct_cumplimiento, clasificacion, agentes:agente_id(nombre_norm, nombre_display), campaigns:campaign_id(anio_campania, fecha_snapshot)"
    ).execute().data or []
    hist: dict[str, dict] = {}
    for r in d:
        ag = r.get("agentes") or {}
        norm = ag.get("nombre_norm")
        if not norm:
            continue
        camp = r.get("campaigns") or {}
        # El eje de evolución es el día (snapshot); cae a anio_campania si falta.
        etiqueta = camp.get("fecha_snapshot") or camp.get("anio_campania", "?")
        entry = hist.setdefault(norm, {"display": ag.get("nombre_display") or norm, "puntos": []})
        entry["puntos"].append({
            "anio": etiqueta,
            "contacto": r["tasa_contacto"], "cumplimiento": r["pct_cumplimiento"], "clasificacion": r["clasificacion"],
        })
    for e in hist.values():
        e["puntos"].sort(key=lambda x: x["anio"])
    return hist


# ── Persistencia idempotente ──
def _chunks(rows: list[dict], n: int = 1000):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def persist_campaign(db: Client, org_id: str, anio: str, nombre: str, cargado_por: str | None,
                     ingest, metrics: dict, fecha_snapshot: str | None = None) -> str:
    # Snapshot diario: la llave es (org, anio_campania, fecha_snapshot). Recargar
    # el mismo día reemplaza esa foto; otro día crea una nueva (§ migración 0004).
    snapshot = fecha_snapshot or _date.today().isoformat()
    camp = db.table("campaigns").upsert({
        "org_id": org_id, "anio_campania": anio, "nombre": nombre,
        "fecha_snapshot": snapshot,
        "fecha_liberacion": ingest.profile.get("fecha_liberacion"),
        "fecha_corte_datos": ingest.profile.get("fecha_corte_datos"),
        "saldo_asignado": ingest.header["saldo_asignado"], "deudas": ingest.header["deudas"],
        "consultoras": ingest.header["consultoras"], "cargado_por": cargado_por,
    }, on_conflict="org_id,anio_campania,fecha_snapshot").execute().data
    campaign_id = camp[0]["id"]

    for t in ["cartera", "pagos", "toques", "gestiones", "agentes", "costo_marcador",
              "metrics_canal", "metrics_agente", "metrics_temporalidad", "metrics_diaria",
              "metrics_secuencia", "metrics_resumen", "quality_flags"]:
        db.table(t).delete().eq("campaign_id", campaign_id).execute()

    # agentes → id
    agente_id: dict[str, str] = {}
    if ingest.agentes:
        rows = [{"campaign_id": campaign_id, "nombre_norm": a["nombre_norm"],
                 "nombre_display": a["nombre_display"], "fuentes": a["fuentes"]} for a in ingest.agentes]
        data = db.table("agentes").insert(rows).execute().data or []
        agente_id = {r["nombre_norm"]: r["id"] for r in data}

    for ch in _chunks([{"campaign_id": campaign_id, "dama_deuda": c["dama_deuda"], "num_dama": c["num_dama"],
                        "saldo_cobro": c["saldo_cobro"], "zona": c["zona"], "ruta": c["ruta"],
                        "fecha_entrega": c["fecha_entrega"]} for c in ingest.cartera]):
        db.table("cartera").insert(ch).execute()
    for ch in _chunks([{"campaign_id": campaign_id, "dama_deuda": p["dama_deuda"], "num_dama": p["num_dama"],
                        "id_cobrador": p["id_cobrador"], "fecha_pago": p["fecha_pago"],
                        "saldo_remanente": p["saldo_remanente"], "estado_proceso": p["estado_proceso"],
                        "recuperado": p["recuperado"]} for p in ingest.pagos]):
        db.table("pagos").insert(ch).execute()
    for ch in _chunks([{"campaign_id": campaign_id, "num_dama": t["num_dama"], "canal": t["canal"],
                        "dia": t["dia"], "efectivo": t["efectivo"], "meta": t["meta"]} for t in ingest.toques]):
        db.table("toques").insert(ch).execute()
    for ch in _chunks([{"campaign_id": campaign_id, "agente_id": agente_id.get(g["agente_norm"]) if g["agente_norm"] else None,
                        "num_dama": g["num_dama"], "fecha": g["fecha"], "tipo_gestion": g["tipo_gestion"],
                        "tipificacion": g["tipificacion"], "promesa_fecha": g["promesa_fecha"],
                        "monto_prometido": g["monto_prometido"], "temp": g["temp"]} for g in ingest.gestiones]):
        db.table("gestiones").insert(ch).execute()

    cm = ingest.profile["costo_marcador"]
    db.table("costo_marcador").insert({"campaign_id": campaign_id, "llamadas": cm["llamadas"],
                                       "minutos": cm["minutos"], "contactos_efectivos": cm["contactos_efectivos"]}).execute()

    if metrics["canal"]:
        db.table("metrics_canal").insert([{"campaign_id": campaign_id, "canal": m["canal"],
            "monto_ultimo_toque": m["monto_ultimo_toque"], "pagos": m["pagos"], "consultoras": m["consultoras"],
            "pct": m["pct"], "eficiencia_por_toque": m["eficiencia_por_toque"],
            "influencia_monto": m["influencia_monto"], "influencia_pct": m["influencia_pct"]} for m in metrics["canal"]]).execute()

    if metrics["agentes"]:
        db.table("metrics_agente").insert([{"campaign_id": campaign_id, "agente_id": agente_id.get(a["agente_id"]),
            "gestiones": a["gestiones"], "contactos_efectivos": a["contactos_efectivos"], "tasa_contacto": a["tasa_contacto"],
            "pdp": a["pdp"], "pdp_cumplidas": a["pdp_cumplidas"], "pct_cumplimiento": a["pct_cumplimiento"],
            "recuperado_atribuido": a["recuperado_atribuido"], "pagadoras": 0, "clasificacion": a["clasificacion"],
            "percentil_contacto": a["percentil_contacto"], "percentil_cumplimiento": a["percentil_cumplimiento"],
            "mentor_sugerido": agente_id.get(a["mentor_sugerido"]) if a["mentor_sugerido"] else None}
            for a in metrics["agentes"] if agente_id.get(a["agente_id"])]).execute()

    if metrics["temporalidad"]:
        db.table("metrics_temporalidad").insert([{"campaign_id": campaign_id, **t} for t in metrics["temporalidad"]]).execute()
    if metrics["diaria"]:
        db.table("metrics_diaria").insert([{"campaign_id": campaign_id, **d} for d in metrics["diaria"]]).execute()
    if metrics["secuencias"]:
        db.table("metrics_secuencia").insert([{"campaign_id": campaign_id, **s} for s in metrics["secuencias"]]).execute()

    db.table("metrics_resumen").insert({"campaign_id": campaign_id, **metrics["resumen"]}).execute()

    if ingest.flags:
        db.table("quality_flags").insert([{"campaign_id": campaign_id, **f} for f in ingest.flags]).execute()

    return campaign_id
