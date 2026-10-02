#!/usr/bin/env python
"""Generate price-list preview images and save them to the project root.

Usage:
    uv run python scripts/preview_lista_precios.py

Requires GARAY_DATABASE_URL in .env or environment.
Outputs up to 4 PNG files: preview_g1_interna.png, preview_g1_turista.png,
preview_g2_interna.png, preview_g2_turista.png
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from garay.aplicacion.servicios.lista_precios import _GRUPO_1_CATEGORIAS
from garay.config import obtener_settings
from garay.dominio.servicios.entidades import TipoImagen
from garay.infraestructura.imagenes.generador_playwright import PlaywrightGeneradorImagen
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from garay.infraestructura.persistencia.repositorios.servicios import SQLAServicioRepository

OUT_DIR = Path(__file__).parent.parent


async def main() -> None:
    settings = obtener_settings()
    if not settings.database_url:
        raise SystemExit("GARAY_DATABASE_URL not set.")

    engine = crear_engine(settings.database_url)
    sf = crear_fabrica_sesiones(engine)
    repo = SQLAServicioRepository(sf)
    todos = repo.listar_activos()

    filtrados = [
        s for s in todos
        if s.activo
        and s.precio_neto_adulto is not None
        and s.precio_sugerido_adulto is not None
    ]

    grupo1 = [s for s in filtrados if s.categoria in _GRUPO_1_CATEGORIAS]
    grupo2 = [s for s in filtrados if s.categoria not in _GRUPO_1_CATEGORIAS]

    print(f"Grupo 1: {len(grupo1)} servicios | Grupo 2: {len(grupo2)} servicios")

    generador = PlaywrightGeneradorImagen()
    names = {
        (0, TipoImagen.INTERNA):  "preview_g1_interna.png",
        (0, TipoImagen.TURISTA):  "preview_g1_turista.png",
        (1, TipoImagen.INTERNA):  "preview_g2_interna.png",
        (1, TipoImagen.TURISTA):  "preview_g2_turista.png",
    }

    for i, grupo in enumerate((grupo1, grupo2)):
        if not grupo:
            print(f"Grupo {i + 1} vacío, saltando.")
            continue
        for tipo in (TipoImagen.INTERNA, TipoImagen.TURISTA):
            print(f"Generando grupo {i + 1} {tipo.value}...", end=" ", flush=True)
            png = await generador.generar_imagen_precios(grupo, tipo)
            out = OUT_DIR / names[(i, tipo)]
            out.write_bytes(png)
            print(f"-> {out.name} ({len(png) // 1024} KB)")

    print("Listo.")


asyncio.run(main())
