"""Modo demo: genera 2 campañas sintéticas y calcula sus métricas en memoria,
con los mismos shapes que devuelven las tablas de Supabase. Permite ver toda la
UI sin backend configurado. La misma generación alimenta scripts/seed.py.
"""
from __future__ import annotations

import pandas as pd

from .ingest import build_ingest
from .metrics import compute_metrics

AGENTES = ["María Pérez", "Juan Gómez", "Ana Ruiz", "Luis Torres", "Sofía Díaz"]
TEMPS = ["Mora 1", "Mora 2", "Mora 3", "MNI", "IM"]


def _rng(seed: int):
    s = seed & 0xFFFFFFFF

    def nxt():
        nonlocal s
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        return s / 0xFFFFFFFF

    return nxt


def synth(anio: str, seed: int) -> dict[str, pd.DataFrame]:
    r = _rng(seed)
    N = 60
    cartera, pagos, gestiones, vicidial, ivr, sms = [], [], [], [], [], []
    for i in range(N):
        num = 100000 + i + seed * 1000
        dama = f"{num}-{anio}"
        saldo = round(500 + r() * 4500)
        temp = TEMPS[int(r() * len(TEMPS))]
        cartera.append({"FechaEntrega": 20250601, "NumDama": num, "AnioCampaniaSaldo": anio,
                        "SaldoCobro": saldo, "NumeroZonaFacturacion": f"Z{i % 5 + 1}", "Ruta": f"R{i % 9 + 1}", "Dama-deuda": dama})
        ultimo = None
        if r() < 0.7:
            dia = 1 + int(r() * 25)
            ultimo = dia
            es_c = r() < 0.55
            fecha = f"2025-06-{dia:02d} 10:15:00"
            promesa = f"{dia + 2:02d}/06/2025" if (es_c and r() < 0.6) else None
            ag = AGENTES[int(r() * len(AGENTES))]
            gestiones.append({"FECHA": fecha, "NOMBRE GESTOR": ag, "CODIGO": num, "zona": f"Z{i % 5 + 1}",
                              "ruta": f"R{i % 9 + 1}", "temp": temp, "TIPO DE GESTION": "CONTACTO" if es_c else "NO CONTACTO",
                              "TELEFONO": "55", "Estatus": "OK", "TIPIFICACIlON": "PROMESA DE PAGO" if es_c else "NO CONTESTA",
                              "COMENTARIO": "", "DIA PROM": "", "MEDICION": "", "PROMESA": promesa})
            vicidial.append({"call_date": fecha, "phone_number_dialed": num, "status": "SALE" if es_c else "NA",
                             "user": f"u{AGENTES.index(ag) + 1}", "full_name": ag, "campaign_id": anio,
                             "length_in_sec": int(r() * 180), "status_name": "Contacto" if es_c else "No contesta"})
        if r() < 0.5:
            dia = 1 + int(r() * 25)
            status = "Contacto" if r() < 0.4 else "No contesta"
            if status == "Contacto":
                ultimo = max(ultimo or 0, dia)
            ivr.append({"Nodama": num, "Saldo": saldo, "Temp": temp, "Ola / Intento": 1,
                        "Estado de la Llamada": status, "Fecha de la Llamada": f"{dia:02d}/06/2025 09:00",
                        "Estado Final": status, "Respuesta DTMF": "1" if r() < 0.3 else "", "Status": status})
        if r() < 0.6:
            dia = 1 + int(r() * 25)
            ok = r() < 0.9
            if ok:
                ultimo = max(ultimo or 0, dia)
            sms.append({"Proyecto": "Arabela", "Fecha Base": "2025-06-01", "Telefono": "55", "Dama": num,
                        "Fecha Envio": f"2025-06-{dia:02d} 08:00:00", "Costo": 0.25, "Mensajes Enviados": 1,
                        "Descripcion": "Exitoso" if ok else "Fallido", "Operador": "Telcel"})
        if r() < 0.45:
            fuera = r() < 0.2
            if fuera:
                pay = f"202507{1 + int(r() * 6):02d}"
            elif ultimo:
                pay = f"202506{min(30, ultimo + int(r() * 5)):02d}"
            else:
                pay = f"202506{10 + int(r() * 18):02d}"
            liq = r() < 0.6
            pagos.append({"IdCobrador": f"C{1 + int(r() * 4)}", "FechaEntrega": int(pay), "NumDama": num,
                          "AnioCampaniaSaldo": anio, "SaldoCampania": 0 if liq else round(saldo * (0.3 + r() * 0.4)),
                          "EstadoProceso": "R" if r() < 0.5 else "E", "Dama-deuda": dama})
    for k in range(300):
        vicidial.append({"call_date": f"2025-06-{1 + k % 25:02d} 11:00:00", "phone_number_dialed": 100000 + k % N,
                         "status": "NA", "user": "VDAD", "full_name": "Outbound Auto Dial", "campaign_id": anio,
                         "length_in_sec": int(r() * 20), "status_name": "No contesta"})
    pagos.append({"IdCobrador": "C1", "FechaEntrega": 20250115, "NumDama": 999999, "AnioCampaniaSaldo": "2025C11",
                  "SaldoCampania": 0, "EstadoProceso": "R", "Dama-deuda": "999999-2025C11"})
    return {k: pd.DataFrame(v) for k, v in
            {"cartera": cartera, "pagos": pagos, "gestiones": gestiones, "vicidial": vicidial, "ivr": ivr, "sms": sms}.items()}


def build_demo() -> dict:
    """Devuelve un store en memoria con shape idéntico a las tablas de Supabase."""
    campaigns = []
    data: dict[str, dict] = {}
    hist_puntos: dict[str, dict] = {}

    # Snapshots DIARIOS: la campaña 2025C12 se carga varios días conforme madura,
    # más un segundo día de otra campaña para la comparativa cruzada.
    SNAPSHOTS = [
        ("2025C12", "2025-06-26", 120, "Campaña 12 · 2025"),
        ("2025C12", "2025-06-27", 121, "Campaña 12 · 2025"),
        ("2025C12", "2025-06-28", 122, "Campaña 12 · 2025"),
        ("2025C13", "2025-06-28", 130, "Campaña 13 · 2025"),
    ]

    for anio, snap, seed, nombre in SNAPSHOTS:
        ing = build_ingest(synth(anio, seed))
        m = compute_metrics(ing)
        cid = f"{anio}@{snap}"
        camp = {
            "id": cid, "anio_campania": anio, "nombre": nombre, "fecha_snapshot": snap,
            "fecha_liberacion": ing.profile["fecha_liberacion"], "fecha_corte_datos": ing.profile["fecha_corte_datos"],
            "saldo_asignado": ing.header["saldo_asignado"], "deudas": ing.header["deudas"], "consultoras": ing.header["consultoras"],
        }
        campaigns.append(camp)

        canal = [{"canal": c["canal"], "monto_ultimo_toque": c["monto_ultimo_toque"], "pagos": c["pagos"],
                  "consultoras": c["consultoras"], "pct": c["pct"], "eficiencia_por_toque": c["eficiencia_por_toque"],
                  "influencia_monto": c["influencia_monto"], "influencia_pct": c["influencia_pct"]} for c in m["canal"]]
        agentes = [{**a, "nombre": a["nombre"], "mentor_nombre": _mentor_nombre(a, m["agentes"])} for a in m["agentes"]]

        data[cid] = {
            "resumen": m["resumen"], "canal": canal, "agentes": agentes,
            "temporalidad": m["temporalidad"], "diaria": m["diaria"], "secuencias": m["secuencias"],
            "flags": ing.flags, "costo_marcador": {"llamadas": ing.profile["costo_marcador"]["llamadas"],
                                                   "minutos": ing.profile["costo_marcador"]["minutos"],
                                                   "contactos_efectivos": ing.profile["costo_marcador"]["contactos_efectivos"]},
        }
        # Evolución del gestor por día (snapshot): solo la campaña principal.
        if anio == "2025C12":
            for a in m["agentes"]:
                entry = hist_puntos.setdefault(a["agente_id"], {"display": a["nombre"], "puntos": []})
                entry["puntos"].append({"anio": snap, "contacto": a["tasa_contacto"],
                                        "cumplimiento": a["pct_cumplimiento"], "clasificacion": a["clasificacion"]})

    for e in hist_puntos.values():
        e["puntos"].sort(key=lambda x: x["anio"])

    return {"campaigns": campaigns, "data": data, "historia": hist_puntos}


def _mentor_nombre(a: dict, agentes: list[dict]) -> str | None:
    if not a.get("mentor_sugerido"):
        return None
    m = next((x for x in agentes if x["agente_id"] == a["mentor_sugerido"]), None)
    return m["nombre"] if m else None
