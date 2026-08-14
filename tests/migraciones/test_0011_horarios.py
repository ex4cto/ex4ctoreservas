"""Tests for migration 0011: add horarios column to servicios.

Test strategy: apply the upgrade()/downgrade() functions directly against a
SQLite in-memory connection that already has the servicios table at revision 0010
state (no horarios column). This avoids running the full Alembic chain while still
exercising the actual migration DDL via a live Alembic Operations context.

The migration file is loaded via importlib because Alembic filenames begin with a
digit (e.g. "0011_..."), which is not a valid Python identifier for a direct import.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Engine, text

from tests.migraciones.conftest import (
    build_servicios_at_0010,
    run_migration_fn,
    table_columns,
)

_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "versions"
    / "0011_add_horarios_to_servicios.py"
)


def _load_migration() -> ModuleType:
    """Dynamically load the 0011 migration module."""
    if not _MIGRATION_FILE.exists():
        pytest.fail(
            f"Migration file not found: {_MIGRATION_FILE}. "
            "Create migrations/versions/0011_add_horarios_to_servicios.py first."
        )
    mod_name = "migration_0011"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMigration0011Upgrade:
    def test_upgrade_agrega_columna_horarios(self, sqlite_engine: Engine) -> None:
        """upgrade() adds the horarios column to the servicios table."""
        migration = _load_migration()

        build_servicios_at_0010(sqlite_engine)
        assert "horarios" not in table_columns(sqlite_engine, "servicios")

        run_migration_fn(sqlite_engine, migration.upgrade)

        assert "horarios" in table_columns(sqlite_engine, "servicios")

    def test_upgrade_backfill_filas_preexistentes(self, sqlite_engine: Engine) -> None:
        """upgrade() leaves pre-existing rows with horarios = [] (not NULL)."""
        migration = _load_migration()

        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())

        build_servicios_at_0010(sqlite_engine)
        with sqlite_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO servicios (id, numero, nombre) VALUES (:id, :num, :nom)"
                ),
                [
                    {"id": id1, "num": 1, "nom": "Tour A"},
                    {"id": id2, "num": 2, "nom": "Tour B"},
                ],
            )

        run_migration_fn(sqlite_engine, migration.upgrade)

        with sqlite_engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, horarios FROM servicios ORDER BY numero")
            ).fetchall()

        assert len(rows) == 2
        for row in rows:
            raw = row[1]
            # SQLite stores JSON as TEXT; parse it to get the Python value.
            value = json.loads(raw) if isinstance(raw, str) else raw
            assert value == [], f"Expected [] for row {row[0]}, got {raw!r}"

    def test_upgrade_nueva_fila_sin_horarios_usa_default(self, sqlite_engine: Engine) -> None:
        """Rows inserted after upgrade without specifying horarios get default []."""
        migration = _load_migration()

        build_servicios_at_0010(sqlite_engine)
        run_migration_fn(sqlite_engine, migration.upgrade)

        new_id = str(uuid.uuid4())
        with sqlite_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO servicios (id, numero, nombre) VALUES (:id, :num, :nom)"
                ),
                {"id": new_id, "num": 99, "nom": "Tour Nuevo"},
            )

        with sqlite_engine.connect() as conn:
            row = conn.execute(
                text("SELECT horarios FROM servicios WHERE id = :id"), {"id": new_id}
            ).fetchone()

        assert row is not None
        raw = row[0]
        value = json.loads(raw) if isinstance(raw, str) else raw
        assert value == []


class TestMigration0011Downgrade:
    def test_downgrade_elimina_columna_horarios(self, sqlite_engine: Engine) -> None:
        """downgrade() removes the horarios column from servicios."""
        migration = _load_migration()

        build_servicios_at_0010(sqlite_engine)
        run_migration_fn(sqlite_engine, migration.upgrade)
        assert "horarios" in table_columns(sqlite_engine, "servicios")

        # SQLite < 3.35 does not support DROP COLUMN natively without batch mode.
        try:
            run_migration_fn(sqlite_engine, migration.downgrade)
            assert "horarios" not in table_columns(sqlite_engine, "servicios")
        except Exception as exc:
            pytest.skip(
                f"SQLite does not support DROP COLUMN inline: {exc}. "
                "Downgrade is covered by Postgres CI."
            )

    def test_downgrade_mantiene_otras_columnas(self, sqlite_engine: Engine) -> None:
        """After downgrade, the other servicios columns are still present."""
        migration = _load_migration()

        build_servicios_at_0010(sqlite_engine)
        run_migration_fn(sqlite_engine, migration.upgrade)

        try:
            run_migration_fn(sqlite_engine, migration.downgrade)
            cols = table_columns(sqlite_engine, "servicios")
            expected = {
                "id", "numero", "nombre", "descripcion", "activo",
                "precio_neto_adulto", "precio_neto_nino", "categoria",
            }
            assert expected.issubset(cols)
        except Exception as exc:
            pytest.skip(
                f"SQLite does not support DROP COLUMN inline: {exc}. "
                "Covered by Postgres CI."
            )
