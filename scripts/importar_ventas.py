#!/usr/bin/env python
"""Importa las ventas historicas de la planilla de contabilidad a la base de datos.

Correr despues de `alembic upgrade head` y `scripts/seed.py`:
    GARAY_DATABASE_URL=... uv run python scripts/importar_ventas.py [ruta.xlsx] [mes] [anio]

Idempotente: usa uuid5 determinista, re-correr es seguro.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from garay.aplicacion.importacion.importar_ventas_excel import ImportarVentasExcelService
from garay.config import obtener_settings
from garay.infraestructura.importacion.lector_excel import LectorVentasExcelOpenpyxl
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from garay.infraestructura.persistencia.repositorios.clientes import SQLAClienteRepository
from garay.infraestructura.persistencia.repositorios.comisiones_registradas import (
    SQLAComisionRegistradaRepository,
)
from garay.infraestructura.persistencia.repositorios.puntos_de_venta import (
    SQLAPuntoDeVentaRepository,
)
from garay.infraestructura.persistencia.repositorios.servicios import SQLAServicioRepository
from garay.infraestructura.persistencia.repositorios.ventas import SQLAVentaRepository

ROOT = Path(__file__).parent.parent
ALIAS = ROOT / "servicios_alias.json"


def main() -> None:
    ruta = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "GARAY-CONTABILIDAD2.xlsx")
    mes = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    anio = int(sys.argv[3]) if len(sys.argv) > 3 else 2026

    settings = obtener_settings()
    if not settings.database_url:
        raise SystemExit("ERROR: GARAY_DATABASE_URL no configurado.")

    engine = crear_engine(settings.database_url)
    sf = crear_fabrica_sesiones(engine)
    alias: dict[str, int] = json.loads(ALIAS.read_text(encoding="utf-8"))

    servicio = ImportarVentasExcelService(
        lector=LectorVentasExcelOpenpyxl(),
        ventas=SQLAVentaRepository(sf),
        clientes=SQLAClienteRepository(sf),
        servicios=SQLAServicioRepository(sf),
        puntos=SQLAPuntoDeVentaRepository(sf),
        comisiones=SQLAComisionRegistradaRepository(sf),
        alias=alias,
    )
    r = servicio.ejecutar(ruta, mes, anio)
    print(
        f"[OK] {r.ventas_creadas} ventas ({r.clientes_creados} clientes nuevos, "
        f"{r.ventas_omitidas} omitidas) | Valor ${r.total_valor.monto:,.0f} | "
        f"Agencia ${r.total_agencia.monto:,.0f}"
    )


if __name__ == "__main__":
    main()
