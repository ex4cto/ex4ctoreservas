"""Tests for scripts/importar_info_tour_csv.py.

Spec ref: "Blank cell -> NULL", "Idempotent re-run", "Unmatched tour -> logged, no crash",
          "Matched tour -> fields updated".
"""

from __future__ import annotations

import csv
import logging
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from scripts.importar_info_tour_csv import _blank_to_none, _normalize, run

# ---------------------------------------------------------------------------
# Helpers — in-memory SQLite DB mirroring migration 0034 schema
# ---------------------------------------------------------------------------


def _make_db() -> sa.engine.Engine:
    """Create an in-memory SQLite DB with the servicios table (post-0034 schema)."""
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            sa.text("""
                CREATE TABLE servicios (
                    id TEXT PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    descripcion TEXT NOT NULL DEFAULT '',
                    activo INTEGER NOT NULL DEFAULT 1,
                    numero INTEGER NOT NULL,
                    precio_neto_adulto REAL,
                    precio_neto_nino REAL,
                    permite_ninos INTEGER NOT NULL DEFAULT 1,
                    categoria TEXT NOT NULL DEFAULT '',
                    horarios TEXT NOT NULL DEFAULT '[]',
                    netos_por_horario TEXT NOT NULL DEFAULT '{}',
                    precio_sugerido_adulto REAL,
                    precio_sugerido_nino REAL,
                    info_tour TEXT,
                    observaciones TEXT
                )
            """)
        )
    return engine


def _seed_servicio(
    engine: sa.engine.Engine,
    nombre: str,
    info_tour: str | None = None,
    observaciones: str | None = None,
) -> str:
    """Insert a servicio row and return its id."""
    sid = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO servicios (id, nombre, numero, descripcion) "
                "VALUES (:id, :nombre, :numero, '')"
            ),
            {"id": sid, "nombre": " ".join(nombre.upper().split()), "numero": 1},
        )
        if info_tour is not None or observaciones is not None:
            conn.execute(
                sa.text(
                    "UPDATE servicios SET info_tour=:info_tour, observaciones=:obs WHERE id=:id"
                ),
                {"info_tour": info_tour, "obs": observaciones, "id": sid},
            )
    return sid


def _read_row(engine: sa.engine.Engine, sid: str) -> dict[str, object]:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT info_tour, observaciones FROM servicios WHERE id=:id"),
            {"id": sid},
        ).fetchone()
    assert row is not None
    return {"info_tour": row[0], "observaciones": row[1]}


def _make_csv(rows: list[dict[str, str]], path: Path) -> None:
    """Write a CSV file with headers matching the real CSV: TOUR, INFORMACION DEL TOUR, OBSERVACIONES."""
    with path.open("w", encoding="latin-1", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["TOUR", "INFORMACION DEL TOUR", "OBSERVACIONES"]
        )
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


def test_blank_to_none_empty_string() -> None:
    assert _blank_to_none("") is None


def test_blank_to_none_whitespace() -> None:
    assert _blank_to_none("   ") is None


def test_blank_to_none_real_content() -> None:
    assert _blank_to_none("Salida 8am") == "Salida 8am"


def test_normalize_uppercases_and_collapses_spaces() -> None:
    assert _normalize("tour  islas") == "TOUR ISLAS"


# ---------------------------------------------------------------------------
# Integration tests using in-memory SQLite
# ---------------------------------------------------------------------------


def test_matched_tour_fields_updated(tmp_path: Path) -> None:
    """Matched tour name -> info_tour and observaciones updated in DB."""
    engine = _make_db()
    sid = _seed_servicio(engine, "TOUR PLANCTON")
    csv_file = tmp_path / "test.csv"
    _make_csv(
        [
            {
                "TOUR": "TOUR PLANCTON",
                "INFORMACION DEL TOUR": "Salida 8am",
                "OBSERVACIONES": "No apto para embarazadas",
            }
        ],
        csv_file,
    )
    run(engine, csv_file)
    row = _read_row(engine, sid)
    assert row["info_tour"] == "Salida 8am"
    assert row["observaciones"] == "No apto para embarazadas"


def test_blank_cell_writes_null(tmp_path: Path) -> None:
    """Blank info_tour cell -> NULL in DB."""
    engine = _make_db()
    sid = _seed_servicio(engine, "TOUR PLAYA", info_tour="previous value")
    csv_file = tmp_path / "test.csv"
    _make_csv(
        [
            {
                "TOUR": "TOUR PLAYA",
                "INFORMACION DEL TOUR": "",
                "OBSERVACIONES": "Some obs",
            }
        ],
        csv_file,
    )
    run(engine, csv_file)
    row = _read_row(engine, sid)
    assert row["info_tour"] is None
    assert row["observaciones"] == "Some obs"


def test_idempotent_rerun(tmp_path: Path) -> None:
    """Running script twice with same CSV produces same state."""
    engine = _make_db()
    sid = _seed_servicio(engine, "TOUR BAHIA")
    csv_file = tmp_path / "test.csv"
    _make_csv(
        [
            {
                "TOUR": "TOUR BAHIA",
                "INFORMACION DEL TOUR": "Info fija",
                "OBSERVACIONES": "Obs fija",
            }
        ],
        csv_file,
    )
    run(engine, csv_file)
    row_first = _read_row(engine, sid)
    run(engine, csv_file)
    row_second = _read_row(engine, sid)
    assert row_first == row_second


def test_unmatched_tour_logs_warning_no_crash(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """CSV row with no matching tour -> warning logged, script does not crash."""
    engine = _make_db()
    csv_file = tmp_path / "test.csv"
    _make_csv(
        [
            {
                "TOUR": "TOUR INEXISTENTE XYZ",
                "INFORMACION DEL TOUR": "Algo",
                "OBSERVACIONES": "",
            }
        ],
        csv_file,
    )
    with caplog.at_level(logging.WARNING):
        run(engine, csv_file)

    assert any("TOUR INEXISTENTE XYZ" in r.message for r in caplog.records)


def test_normalization_case_insensitive_match(tmp_path: Path) -> None:
    """CSV nombre with different casing/spaces matches DB after normalization."""
    engine = _make_db()
    sid = _seed_servicio(engine, "TOP 3 ISLAS")
    csv_file = tmp_path / "test.csv"
    _make_csv(
        [
            {
                "TOUR": "top  3  islas",  # different case and extra spaces
                "INFORMACION DEL TOUR": "Info normalizada",
                "OBSERVACIONES": "",
            }
        ],
        csv_file,
    )
    run(engine, csv_file)
    row = _read_row(engine, sid)
    assert row["info_tour"] == "Info normalizada"
    assert row["observaciones"] is None
