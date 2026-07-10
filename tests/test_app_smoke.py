"""Smoke test de la app Streamlit con AppTest: login → demo → cada página."""
import subprocess
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "streamlit_app.py")
PAGINAS = ["resumen", "canales", "promesas", "secuencias", "gestionado",
           "gestores", "temporalidad", "tendencia", "comparativa", "carga", "metodologia"]


def _demo_app(page="resumen"):
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["_page"] = page  # no-op salvo para variar
    at.run()
    # click "Entrar en modo demo"
    demo_btn = next(b for b in at.button if "demo" in b.label.lower())
    demo_btn.click().run()
    return at


def test_login_shown_first():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("demo" in b.label.lower() for b in at.button)


def test_demo_mode_boots_resumen():
    at = _demo_app()
    assert not at.exception
    assert at.session_state["authed"] is True
    assert at.session_state["demo"] is True
    # el resumen ejecutivo debe existir
    assert any("Resumen ejecutivo" in m.value for m in at.markdown)


_PROBE = """
from streamlit.testing.v1 import AppTest
probe = '''
import streamlit as st
from cobranza import theme
from cobranza.demo import build_demo
from app_pages import {page}
theme.inject()
st.session_state.setdefault("authed", True)
st.session_state.setdefault("demo", True)
st.session_state.setdefault("store", build_demo())
st.session_state.setdefault("profile", {{"rol": "admin"}})
st.session_state.setdefault("cid", "2025C12")
{page}.render()
'''
at = AppTest.from_string(probe, default_timeout=30).run()
assert not at.exception, str(at.exception)
print("OK")
"""


@pytest.mark.parametrize("page", PAGINAS)
def test_page_renders_without_exception(page):
    # Cada página se renderiza en un subproceso aislado: correr muchos AppTest
    # en un mismo intérprete provoca un segfault de pyarrow en teardown.
    res = subprocess.run(
        [sys.executable, "-c", _PROBE.format(page=page)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120,
    )
    assert res.returncode == 0 and "OK" in res.stdout, f"[{page}] {res.stderr[-800:]}"
