"""Seed / demostración end-to-end (Python).

Si /data/seed trae los 6 .xlsx reales, los usa; si no, GENERA una campaña
sintética (dos, para la comparativa) con los shapes de §3. Corre el pipeline
+ métricas e imprime el perfilado. Si hay credenciales de Supabase, persiste.

Uso:  python scripts/seed.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cobranza.demo import synth  # noqa: E402
from cobranza.ingest import build_ingest, read_sheet  # noqa: E402
from cobranza.metrics import compute_metrics  # noqa: E402

SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seed"
FILE_PATTERNS = {
    "cartera": "cartera", "pagos": "pago", "gestiones": "gestion",
    "vicidial": "vicidial", "ivr": "reminder", "sms": "sms",
}


def load_real() -> dict[str, pd.DataFrame] | None:
    if not SEED_DIR.exists():
        return None
    files = [f for f in SEED_DIR.glob("*.xlsx") if not f.name[0:1].isupper() or "_2025C1" not in f.name]
    sheets = {}
    for key, pat in FILE_PATTERNS.items():
        hit = next((f for f in SEED_DIR.glob("*.xlsx") if pat in f.name.lower() and "_2025c1" not in f.name.lower()), None)
        if hit:
            sheets[key] = read_sheet(hit)
    if len(sheets) == 6:
        print("→ Usando archivos reales de /data/seed")
        return sheets
    return None


def report(label: str, sheets: dict[str, pd.DataFrame]):
    print(f"\n══════════ {label} ══════════")
    ing = build_ingest(sheets)
    m = compute_metrics(ing)
    print("Filas:", ing.profile["filas"])
    print("Tasas de cruce:", {k: round(v, 2) for k, v in ing.profile["cruces"].items()})
    print("Corte de datos de canal:", ing.profile["fecha_corte_datos"], "| máx pago:", ing.profile["fecha_max_pago"])
    print("C3 · costo marcador:", ing.profile["costo_marcador"])
    print("Flags de calidad:")
    for f in ing.flags:
        print(f"  [{f['severidad']}] {f['tipo']}: {f['detalle']}")
    print("Recuperado total:", round(m["resumen"]["recuperado"]))
    print("Mezcla por canal (último toque):")
    for c in m["canal"]:
        print(f"  {c['canal']:<11} {round(c['monto_ultimo_toque']):>8}  {c['pct'] * 100:.1f}%")
    print(f"% espontáneo: {m['resumen']['pct_espontaneo'] * 100:.1f}% | % fuera de ventana: "
          f"{m['resumen']['pct_fuera_ventana'] * 100:.1f}% | % cartera no contactada: {m['resumen']['pct_cartera_no_contactada'] * 100:.1f}%")
    print("Gestores (cuadrante):")
    for a in m["agentes"]:
        extra = f" → mentor:{a['mentor_sugerido']}" if a["mentor_sugerido"] else ""
        print(f"  {a['nombre']:<14} contacto={a['tasa_contacto'] * 100:.0f}%  cumpl={a['pct_cumplimiento'] * 100:.0f}%  {a['clasificacion']}{extra}")
    return ing, m


def main():
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    real = load_real()
    if real:
        ing, m = report("Campaña real (/data/seed)", real)
        _maybe_persist([(ing.cartera[0]["dama_deuda"].split("-")[1] if ing.cartera else "REAL", ing, m)])
        return

    c12 = synth("2025C12", 12)
    c13 = synth("2025C13", 13)
    for key, df in c12.items():
        df.to_excel(SEED_DIR / f"{key.capitalize()}_2025C12.xlsx", index=False)
    print("→ .xlsx sintéticos escritos en data/seed/ (campaña 2025C12).")

    i12, m12 = report("Campaña 2025C12 (sintética)", c12)
    i13, m13 = report("Campaña 2025C13 (sintética)", c13)
    _maybe_persist([("2025C12", i12, m12), ("2025C13", i13, m13)])


def _maybe_persist(items):
    if not os.environ.get("DATABASE_URL"):
        print("\n(Neon no configurado: no se persistió. Rellena DATABASE_URL en .env / secrets para persistir.)")
        return
    from cobranza.db import DEFAULT_ORG, persist_campaign
    for anio, ing, m in items:
        cid = persist_campaign(DEFAULT_ORG, anio, f"Campaña {anio}", None, ing, m)
        print(f"✓ Persistida {anio} → {cid}")


if __name__ == "__main__":
    main()
