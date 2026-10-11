"""Cruce completo entre seed, BD local y BD produccion."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from garay.config import obtener_settings
from garay.infraestructura.persistencia.modelos import ServicioModel
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from sqlalchemy import select

ROOT = Path(__file__).parent.parent

# --- Seed ---
seed = json.loads((ROOT / "servicios_seed.json").read_text(encoding="utf-8"))
seed_by_num: dict[int, dict] = {s["numero"]: s for s in seed}

# --- Local SQLite ---
conn = sqlite3.connect(ROOT / "garay_local.db")
cur = conn.cursor()
cur.execute("SELECT numero, nombre, activo FROM servicios ORDER BY numero")
local_rows = cur.fetchall()
conn.close()
local_by_num = {r[0]: {"nombre": r[1], "activo": bool(r[2])} for r in local_rows}

# --- Produccion ---
engine = crear_engine(obtener_settings().database_url)
with crear_fabrica_sesiones(engine)() as s:
    prod_rows = s.execute(select(ServicioModel).order_by(ServicioModel.numero)).scalars().all()
prod_by_num = {r.numero: r for r in prod_rows}

all_nums = sorted(set(seed_by_num) | set(local_by_num) | set(prod_by_num))

print(f"{'#':>4}  {'SEED':<45} {'LOCAL':<45} {'PROD':<45} {'DIFF'}")
print("-" * 180)

for n in all_nums:
    s_nom = seed_by_num[n]["nombre"] if n in seed_by_num else "(no en seed)"
    l_nom = local_by_num[n]["nombre"] if n in local_by_num else "(no en local)"
    p_nom = prod_by_num[n].nombre if n in prod_by_num else "(no en prod)"

    diffs = []
    if s_nom != l_nom:
        diffs.append("S≠L")
    if s_nom != p_nom:
        diffs.append("S≠P")
    if l_nom != p_nom:
        diffs.append("L≠P")

    if diffs or "(no en" in f"{s_nom}{l_nom}{p_nom}":
        diff_str = " ".join(diffs).replace("≠", "!=")
        print(f"{n:>4}  {s_nom[:44]:<45} {l_nom[:44]:<45} {p_nom[:44]:<45} {diff_str}")

print()
print(f"Seed: {len(seed_by_num)} | Local: {len(local_by_num)} | Prod: {len(prod_by_num)}")

print("\n--- Datos completos #83 y #166 en produccion ---")
for n in [83, 166]:
    if n in prod_by_num:
        r = prod_by_num[n]
        print(f"#{n}: nombre={r.nombre!r} activo={r.activo} cat={r.categoria!r}")
        print(f"     neto_a={r.precio_neto_adulto} neto_n={r.precio_neto_nino} permite_n={r.permite_ninos}")
        print(f"     sug_a={r.precio_sugerido_adulto} sug_n={r.precio_sugerido_nino}")
