"""Idempotent script to import info_tour and observaciones fields from CSV into the DB.

Usage:
    DATABASE_URL=postgresql://... python scripts/importar_info_tour_csv.py

The CSV file is expected at the repo root with columns:
    TOUR               — tour name (normalized with upper().split() join)
    INFORMACION DEL TOUR — maps to info_tour (blank -> NULL)
    OBSERVACIONES      — maps to observaciones (blank -> NULL)

Matching is done by normalizing both the CSV nombre and the DB nombre using the
same rule as Servicio.__post_init__: ' '.join(nombre.upper().split()).
Blank or whitespace-only cells are stored as NULL.
Unmatched tour names are logged as warnings and do not crash the script.
The script is idempotent: running it multiple times with the same CSV produces
the same DB state.
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path

import sqlalchemy as sa

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_CSV_PATH = Path(__file__).parent.parent / "GARAY-CONTABILIDAD2 - Copia de PRECIOS (09_26).csv"
_CSV_ENCODING = "latin-1"
_CSV_NOMBRE_COL = "TOUR"
_CSV_INFO_COL = "INFORMACION DEL TOUR"
_CSV_OBS_COL = "OBSERVACIONES"


def _normalize(nombre: str) -> str:
    """Same normalization as Servicio.__post_init__."""
    return " ".join(nombre.upper().split())


def _blank_to_none(value: str) -> str | None:
    """Return None for blank/whitespace-only strings."""
    stripped = value.strip()
    return stripped if stripped else None


def run(
    database_url: str | sa.engine.Engine,
    csv_path: Path = _CSV_PATH,
) -> None:
    """Read the CSV and UPDATE servicios rows with matching names.

    Args:
        database_url: SQLAlchemy-compatible connection string OR an existing Engine.
            Passing an Engine directly is useful for tests where the in-memory
            SQLite DB is already populated.
        csv_path: Path to the CSV file (latin-1 encoded).
    """
    engine: sa.engine.Engine = (
        sa.create_engine(database_url) if isinstance(database_url, str) else database_url
    )

    # Load DB rows into a {normalized_nombre: id} mapping.
    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT id, nombre FROM servicios")).fetchall()

    db_map: dict[str, str] = {_normalize(r[1]): str(r[0]) for r in rows}
    logger.info("Loaded %d servicios from database", len(db_map))

    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        sys.exit(1)

    updated = 0
    unmatched: list[str] = []

    with csv_path.open(encoding=_CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            logger.error("CSV has no headers")
            sys.exit(1)

        fieldnames = list(reader.fieldnames)
        missing = [c for c in (_CSV_NOMBRE_COL, _CSV_INFO_COL, _CSV_OBS_COL) if c not in fieldnames]
        if missing:
            logger.error(
                "CSV missing required columns %s. Found: %s", missing, fieldnames
            )
            sys.exit(1)

        with engine.begin() as conn:
            for row in reader:
                raw_nombre = row.get(_CSV_NOMBRE_COL, "")
                normalized = _normalize(raw_nombre)
                if not normalized:
                    continue

                servicio_id = db_map.get(normalized)
                if servicio_id is None:
                    unmatched.append(raw_nombre)
                    logger.warning(
                        "Unmatched tour name: %r (normalized: %r)",
                        raw_nombre,
                        normalized,
                    )
                    continue

                info_tour = _blank_to_none(row.get(_CSV_INFO_COL, ""))
                observaciones = _blank_to_none(row.get(_CSV_OBS_COL, ""))

                conn.execute(
                    sa.text(
                        "UPDATE servicios "
                        "SET info_tour = :info_tour, observaciones = :observaciones "
                        "WHERE id = :id"
                    ),
                    {
                        "info_tour": info_tour,
                        "observaciones": observaciones,
                        "id": servicio_id,
                    },
                )
                updated += 1
                info_preview = (
                    info_tour[:40] + "..." if info_tour and len(info_tour) > 40 else info_tour
                )
                obs_preview = (
                    observaciones[:40] + "..."
                    if observaciones and len(observaciones) > 40
                    else observaciones
                )
                logger.info(
                    "Updated %r: info_tour=%r, observaciones=%r",
                    raw_nombre,
                    info_preview,
                    obs_preview,
                )

    logger.info(
        "Done. %d rows updated, %d unmatched.", updated, len(unmatched)
    )


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL")
    if not url:
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)
    run(url)
