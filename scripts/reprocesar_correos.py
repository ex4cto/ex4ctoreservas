#!/usr/bin/env python
"""Reprocess quarantined emails that could not be parsed when they arrived.

Run via:
    railway run python scripts/reprocesar_correos.py

Reads all rows from correos_no_parseados where procesado=False and
intentos < MAX_INTENTOS, retries parsing, and persists any that now succeed.

Requires GARAY_DATABASE_URL set in environment or .env file.
"""

from __future__ import annotations

import os

from garay.config import obtener_settings
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from garay.infraestructura.persistencia.repositorios.correos_no_parseados import (
    SQLACorreoNoParseadoRepository,
)
from garay.infraestructura.persistencia.repositorios.egresos import SQLAEgresoRepository
from garay.infraestructura.persistencia.repositorios.ingresos import SQLAIngresoRepository
from garay.infraestructura.webhook.reproceso import reprocesar_pendientes

# Maximum number of failed parse attempts before a row is excluded from reprocessing.
# Override via MAX_INTENTOS environment variable.
_DEFAULT_MAX_INTENTOS = 5


def main() -> None:
    max_intentos = int(os.environ.get("MAX_INTENTOS", _DEFAULT_MAX_INTENTOS))

    settings = obtener_settings()
    if not settings.database_url:
        raise SystemExit(
            "ERROR: GARAY_DATABASE_URL not configured. Create .env from env.example."
        )

    engine = crear_engine(settings.database_url)
    sf = crear_fabrica_sesiones(engine)

    correo_repo = SQLACorreoNoParseadoRepository(sf)
    ingreso_repo = SQLAIngresoRepository(sf)
    egreso_repo = SQLAEgresoRepository(sf)

    print(f"Reprocessing quarantined emails (max_intentos={max_intentos}) ...")

    resultado = reprocesar_pendientes(
        correo_repo=correo_repo,
        ingreso_repo=ingreso_repo,
        egreso_repo=egreso_repo,
        moneda=settings.moneda_predeterminada,
        max_intentos=max_intentos,
    )

    total = resultado.recuperados + resultado.ya_existian + resultado.fallidos
    print(
        f"[OK] {total} rows processed — "
        f"recovered: {resultado.recuperados}, "
        f"already_existed: {resultado.ya_existian}, "
        f"failed: {resultado.fallidos}"
    )


if __name__ == "__main__":
    main()
