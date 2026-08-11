"""Nueva cartera: cuentas no tocadas (sin contacto efectivo) Y sin pago."""
import io

import pandas as pd

from cobranza.analytics import _cartera_no_trabajada
from cobranza.export import cartera_nueva_xlsx, cartera_nueva_filename
from cobranza.brands import ARABELA, NATURA


def _cartera(*nums):
    return [{"num_dama": n, "dama_deuda": f"{n}-2025C12", "saldo_cobro": 100.0 * n,
             "zona": "Z1", "ruta": "R1"} for n in nums]


def test_incluye_solo_no_tocadas_y_sin_pago():
    cartera = _cartera(1, 2, 3, 4)
    ef_por_dama = {2: [{"canal": "Llamada", "dia": "2025-06-10"}]}  # 2 fue tocada (efectivo)
    pago_dia = {3: "2025-06-12"}                                     # 3 pagó
    temp_dama = {1: "Mora 2"}
    cn = _cartera_no_trabajada(cartera, ef_por_dama, pago_dia, temp_dama)
    nums = {f["num_dama"] for f in cn["filas"]}
    # 1 y 4: ni tocadas ni pagaron → entran. 2 tocada, 3 pagó → fuera.
    assert nums == {1, 4}
    assert cn["cuentas"] == 2
    assert cn["saldo_total"] == 100.0 * 1 + 100.0 * 4
    assert cn["pct_cuentas"] == 2 / 4
    # temporalidad se arrastra cuando existe
    fila1 = next(f for f in cn["filas"] if f["num_dama"] == 1)
    assert fila1["temporalidad"] == "Mora 2"


def test_ordena_por_saldo_descendente():
    cn = _cartera_no_trabajada(_cartera(1, 5, 3), {}, {}, {})
    saldos = [f["saldo"] for f in cn["filas"]]
    assert saldos == sorted(saldos, reverse=True)


def test_cartera_toda_trabajada_queda_vacia():
    cartera = _cartera(1, 2)
    cn = _cartera_no_trabajada(cartera, {1: [{}]}, {2: "2025-06-10"}, {})
    assert cn["cuentas"] == 0
    assert cn["filas"] == []


def test_xlsx_terminologia_por_marca():
    cn = _cartera_no_trabajada(_cartera(1, 2), {}, {}, {})
    camp = {"anio_campania": "2025C12", "fecha_snapshot": "2025-06-28"}
    # Arabela → Dama
    xb = cartera_nueva_xlsx(cn, ARABELA, camp)
    df = pd.read_excel(io.BytesIO(xb))
    assert "NumDama" in df.columns and "Dama-deuda" in df.columns and len(df) == 2
    # Natura → Consultora
    xn = cartera_nueva_xlsx(cn, NATURA, camp)
    dn = pd.read_excel(io.BytesIO(xn))
    assert "NumConsultora" in dn.columns and "Consultora-deuda" in dn.columns
    assert "natura" in cartera_nueva_filename(NATURA, camp)


def test_xlsx_vacio_conserva_encabezados():
    cn = {"cuentas": 0, "saldo_total": 0.0, "pct_cuentas": 0.0, "filas": []}
    xb = cartera_nueva_xlsx(cn, ARABELA, {"anio_campania": "x", "fecha_snapshot": "y"})
    df = pd.read_excel(io.BytesIO(xb))
    assert list(df.columns)[:2] == ["NumDama", "Dama-deuda"]
    assert len(df) == 0
