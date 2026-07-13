"""Pruebas de parseo real (formatos de los archivos de producción)."""
import pandas as pd

from cobranza.coerce import to_iso_date
from cobranza.ingest import _parse_promesa, build_ingest
from cobranza.predicates import ivr_efectivo


def test_to_iso_date_guarda_nat():
    # El bug: NaT devolvía el texto "NaT" y quedaba como fecha máxima.
    assert to_iso_date(pd.NaT) is None
    assert to_iso_date(float("nan")) is None
    assert to_iso_date("2026-07-08 10:00:00") == "2026-07-08"
    assert to_iso_date(20260701) == "2026-07-01"


def test_ivr_efectivo_vicidial_status_name():
    # No-contacto automático del blaster → no efectivo.
    for s in ["Ocupado automatico", "Buzon automatico", "No Answer AutoDial",
              "Agente no disponible", "Outbound Pre-Routing Drop", "No contesta"]:
        assert ivr_efectivo(s) is False, s
    # Conectó con persona → efectivo.
    for s in ["Contacto", "Llamada transferida", "PROMESA DE PAGO ", "YA PGO SOLICITAR COMPROBANTE"]:
        assert ivr_efectivo(s) is True, s
    assert ivr_efectivo("") is False


def test_parse_promesa_dia_mes_sin_anio():
    # Formato real "1/07" (día/mes) → toma el año de la fecha de la gestión.
    assert _parse_promesa("1/07", "2026-07-01") == "2026-07-01"
    assert _parse_promesa("15/6", "2026-06-10") == "2026-06-15"
    assert _parse_promesa("01/07/26", None) == "2026-07-01"
    assert _parse_promesa("01/07/2026", None) == "2026-07-01"
    assert _parse_promesa(None, "2026-07-01") is None


def test_gestiones_sistema_y_ivr_vicidial():
    # Mini-dataset con los formatos reales: Sistema excluido, IVR Vicidial leído.
    cartera = pd.DataFrame([
        {"FechaEntrega": 20260701, "NumDama": 100, "AnioCampaniaSaldo": 202614,
         "SaldoCobro": 500, "NumeroZonaFacturacion": 1, "Ruta": 1, "Dama-deuda": 100202614},
    ])
    gestiones = pd.DataFrame([
        {"FECHA": pd.Timestamp("2026-07-02 10:00"), "NOMBRE": "Sistema", "CODIGO": 100,
         "TIPO DE GESTION": "NO CONTACTO", "TIPIFICACIlON": "x", "PROMESA": None, "MEDICION": None, "temp": "Mora 1"},
        {"FECHA": pd.Timestamp("2026-07-03 10:00"), "NOMBRE": "Ana Ruiz", "CODIGO": 100,
         "TIPO DE GESTION": "CONTACTO", "TIPIFICACIlON": "PROMESA", "PROMESA": "5/07", "MEDICION": None, "temp": "Mora 1"},
    ])
    ivr = pd.DataFrame([
        {"call_date": pd.Timestamp("2026-07-04 09:00"), "No. Dama": 100, "status": "AB",
         "status_name": "Ocupado automatico", "full_name": "Outbound Auto Dial"},
        {"call_date": pd.Timestamp("2026-07-05 09:00"), "No. Dama": 100, "status": "XFER",
         "status_name": "Llamada transferida", "full_name": "Outbound Auto Dial"},
    ])
    sms = pd.DataFrame([
        {"Dama": 100.0, "Fecha Envio": pd.Timestamp("2026-07-06 08:00"), "Descripcion": "Exitoso", "Operador": "Telcel"},
    ])
    empty = pd.DataFrame()
    ing = build_ingest({"cartera": cartera, "pagos": empty, "gestiones": gestiones,
                        "vicidial": empty, "ivr": ivr, "sms": sms})

    # Solo Ana Ruiz es gestora (Sistema excluido).
    assert [a["nombre_display"] for a in ing.agentes] == ["Ana Ruiz"]
    # Llamada: solo la gestión de Ana (Sistema no emite toque).
    llamadas = [t for t in ing.toques if t["canal"] == "Llamada"]
    assert len(llamadas) == 1 and llamadas[0]["efectivo"] is True
    # IVR: 2 toques, solo el transferido es efectivo.
    ivr_t = [t for t in ing.toques if t["canal"] == "IVR"]
    assert len(ivr_t) == 2
    assert sum(1 for t in ivr_t if t["efectivo"]) == 1
    # Promesa "5/07" → 2026-07-05.
    proms = [g["promesa_fecha"] for g in ing.gestiones if g["promesa_fecha"]]
    assert proms == ["2026-07-05"]
    # Fecha de corte = máxima fecha de canal (SMS 07-06).
    assert ing.profile["fecha_corte_datos"] == "2026-07-06"
