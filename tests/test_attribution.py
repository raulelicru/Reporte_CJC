"""Cobertura del motor de atribución (C1–C4, empates, ventana 7d, sesgo temporal)."""
import pytest

from cobranza.attribution import (
    Payment,
    Touch,
    VENTANA_DIAS,
    attribute_all,
    attribute_last_touch,
    dif_dias,
    eficiencia_por_toque,
    influence_model,
    resumen_primario,
    sesgo_temporal,
)
from cobranza.normalize import is_auto_dialer, normalize_name
from cobranza.predicates import (
    es_liquidacion,
    gestion_efectiva,
    ivr_efectivo,
    sms_efectivo,
)


def pago(num_dama, fecha_pago, recuperado=100.0):
    return Payment(f"{num_dama}-2025C12", num_dama, fecha_pago, recuperado)


def toque(num_dama, canal, dia, efectivo=True):
    return Touch(num_dama, canal, dia, efectivo)


# ── utilidades de fecha ──
def test_dif_dias_utc():
    assert dif_dias("2025-06-10", "2025-06-03") == 7
    assert dif_dias("2025-06-03", "2025-06-10") == -7
    assert dif_dias("2025-06-10", "2025-06-10") == 0


# ── C1 · contacto efectivo ≠ intento ──
def test_c1_gestion_solo_contacto():
    assert gestion_efectiva("CONTACTO") is True
    assert gestion_efectiva("contacto") is True
    assert gestion_efectiva("NO CONTACTO") is False
    assert gestion_efectiva("") is False


def test_c1_ivr_y_sms():
    assert ivr_efectivo("Contacto") is True
    assert ivr_efectivo("No contesta") is False
    assert sms_efectivo("Exitoso") is True
    assert sms_efectivo("Enviado") is True
    assert sms_efectivo("Fallido") is False


def test_c1_toque_no_efectivo_no_atribuye():
    p = pago(1, "2025-06-10")
    assert attribute_last_touch(p, [toque(1, "Llamada", "2025-06-09", False)])[0] == "Espontaneo"


def test_c1_attribute_all_ignora_no_efectivos():
    res = attribute_all(
        [pago(1, "2025-06-10")],
        [toque(1, "IVR", "2025-06-09", False), toque(1, "SMS", "2025-06-08", True)],
        "2025-06-30",
    )
    assert res[0].canal == "SMS"


# ── C2 · gestiones + vicidial = un solo canal ──
def test_c2_normaliza_nombres():
    assert normalize_name("José  Pérez") == "jose perez"
    assert normalize_name("JOSE PEREZ") == "jose perez"
    assert normalize_name("  María-Núñez ") == "maria nunez"


def test_c2_no_duplica_recuperacion():
    res = attribute_all(
        [pago(1, "2025-06-10", 500)],
        [toque(1, "Llamada", "2025-06-09"), toque(1, "Llamada", "2025-06-08")],
        "2025-06-30",
    )
    llamada = next(r for r in resumen_primario(res) if r["canal"] == "Llamada")
    assert llamada["monto"] == 500  # no 1000
    assert llamada["pagos"] == 1


# ── C3 · marcador automático = costo, no canal ──
def test_c3_identifica_marcador():
    assert is_auto_dialer("Outbound Auto Dial") is True
    assert is_auto_dialer("outbound auto dial") is True
    assert is_auto_dialer("Inbound No Agent") is True
    assert is_auto_dialer("Juan Pérez") is False


# ── C4 · prohibido inflar causalidad ──
def test_c4_pago_sin_contacto_es_espontaneo():
    canal, touch = attribute_last_touch(pago(1, "2025-06-10"), [])
    assert canal == "Espontaneo"
    assert touch is None


def test_c4_toque_posterior_no_atribuye():
    canal, _ = attribute_last_touch(pago(1, "2025-06-10"), [toque(1, "Llamada", "2025-06-11")])
    assert canal == "Espontaneo"


# ── ventana de 7 días ──
def test_ventana_incluye_7_dias():
    assert attribute_last_touch(pago(1, "2025-06-10"), [toque(1, "SMS", "2025-06-03")])[0] == "SMS"


def test_ventana_excluye_8_dias():
    canal, _ = attribute_last_touch(pago(1, "2025-06-11"), [toque(1, "SMS", "2025-06-03")])
    assert canal == "Espontaneo"
    assert dif_dias("2025-06-11", "2025-06-03") == VENTANA_DIAS + 1


def test_elige_toque_mas_reciente():
    canal, _ = attribute_last_touch(
        pago(1, "2025-06-10"),
        [toque(1, "SMS", "2025-06-05"), toque(1, "IVR", "2025-06-09")],
    )
    assert canal == "IVR"


# ── empate el mismo día → Llamada > IVR > SMS ──
def test_empate_llamada_gana():
    canal, _ = attribute_last_touch(
        pago(1, "2025-06-10"),
        [toque(1, "SMS", "2025-06-09"), toque(1, "IVR", "2025-06-09"), toque(1, "Llamada", "2025-06-09")],
    )
    assert canal == "Llamada"


def test_empate_ivr_gana_a_sms():
    canal, _ = attribute_last_touch(
        pago(1, "2025-06-10"),
        [toque(1, "SMS", "2025-06-09"), toque(1, "IVR", "2025-06-09")],
    )
    assert canal == "IVR"


def test_recencia_manda_entre_dias():
    canal, _ = attribute_last_touch(
        pago(1, "2025-06-10"),
        [toque(1, "Llamada", "2025-06-08"), toque(1, "SMS", "2025-06-09")],
    )
    assert canal == "SMS"


# ── modelo secundario · influencia ──
def test_influencia_supera_100():
    payments = [pago(1, "2025-06-10", 1000)]
    touches = [
        toque(1, "Llamada", "2025-05-01"),
        toque(1, "SMS", "2025-05-02"),
        toque(1, "IVR", "2025-05-03"),
    ]
    res = influence_model(payments, touches)
    assert res["total"] == 1000
    suma = sum(c["pct"] for c in res["canales"])
    assert suma == pytest.approx(3.0)


def test_influencia_ignora_no_efectivos():
    res = influence_model([pago(1, "2025-06-10", 1000)], [toque(1, "Llamada", "2025-05-01", False)])
    llamada = next(c for c in res["canales"] if c["canal"] == "Llamada")
    assert llamada["monto"] == 0


# ── sesgo temporal ──
def test_sesgo_temporal():
    payments = [pago(1, "2025-06-28", 100), pago(2, "2025-07-05", 300)]
    s = sesgo_temporal(payments, "2025-06-30")
    assert s["monto_fuera_de_ventana"] == 300
    assert s["monto_total"] == 400
    assert s["pagos_fuera_de_ventana"] == 1
    assert s["pct_fuera_de_ventana"] == pytest.approx(0.75)


def test_attribute_all_marca_fuera_de_ventana():
    res = attribute_all(
        [pago(1, "2025-07-05", 300)],
        [toque(1, "Llamada", "2025-06-30")],
        "2025-06-30",
    )
    assert res[0].fuera_de_ventana is True


# ── eficiencia por toque ──
def test_eficiencia_por_toque():
    atribs = attribute_all(
        [pago(1, "2025-06-10", 300)],
        [toque(1, "Llamada", "2025-06-09"), toque(2, "Llamada", "2025-06-01")],
        "2025-06-30",
    )
    ef = eficiencia_por_toque(atribs, [toque(1, "Llamada", "2025-06-09"), toque(2, "Llamada", "2025-06-01")])
    assert ef["Llamada"] == 150  # 300 / 2 toques


# ── liquidación ──
def test_liquidacion_r_y_e():
    assert es_liquidacion("R") is True
    assert es_liquidacion("E") is True
    assert es_liquidacion("X") is False
