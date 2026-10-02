"""Tests for migration 0030: add precio_sugerido_adulto and precio_sugerido_nino to servicios."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Engine

from tests.migraciones.conftest import (
    run_migration_fn,
    table_columns,
)

_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "versions"
    / "0030_add_precio_sugerido_to_servicios.py"
)


def _load_migration() -> ModuleType:
    if not _MIGRATION_FILE.exists():
        pytest.fail(f"Migration file not found: {_MIGRATION_FILE}.")
    mod_name = "migration_0030"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_servicios_at_0029(engine: Engine) -> None:
    """Create servicios table as it exists at revision 0029 (no sugerido columns).

    Includes permite_ninos (added in 0021) and netos_por_horario (added in 0027),
    so migration 0030 can be tested in isolation.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS servicios (
                id TEXT PRIMARY KEY,
                numero INTEGER NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                descripcion TEXT NOT NULL DEFAULT '',
                activo INTEGER NOT NULL DEFAULT 1,
                precio_neto_adulto NUMERIC(14,2),
                precio_neto_nino NUMERIC(14,2),
                categoria TEXT NOT NULL DEFAULT '',
                horarios JSON NOT NULL DEFAULT '[]',
                permite_ninos INTEGER NOT NULL DEFAULT 1,
                netos_por_horario JSON NOT NULL DEFAULT '{}'
            )
            """)
        )


class TestMigration0030Upgrade:
    def test_upgrade_agrega_precio_sugerido_adulto(self, sqlite_engine: Engine) -> None:
        """upgrade() adds nullable precio_sugerido_adulto column to servicios."""
        build_servicios_at_0029(sqlite_engine)
        assert "precio_sugerido_adulto" not in table_columns(sqlite_engine, "servicios")
        run_migration_fn(sqlite_engine, _load_migration().upgrade)
        assert "precio_sugerido_adulto" in table_columns(sqlite_engine, "servicios")

    def test_upgrade_agrega_precio_sugerido_nino(self, sqlite_engine: Engine) -> None:
        """upgrade() adds nullable precio_sugerido_nino column to servicios."""
        build_servicios_at_0029(sqlite_engine)
        assert "precio_sugerido_nino" not in table_columns(sqlite_engine, "servicios")
        run_migration_fn(sqlite_engine, _load_migration().upgrade)
        assert "precio_sugerido_nino" in table_columns(sqlite_engine, "servicios")

    def test_upgrade_columnas_aceptan_null(self, sqlite_engine: Engine) -> None:
        """After upgrade, inserting a row with NULL sugerido columns succeeds."""
        from sqlalchemy import text

        build_servicios_at_0029(sqlite_engine)
        run_migration_fn(sqlite_engine, _load_migration().upgrade)
        with sqlite_engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO servicios (
                    id, numero, nombre, descripcion, activo,
                    precio_neto_adulto, precio_neto_nino, categoria, horarios,
                    permite_ninos, netos_por_horario,
                    precio_sugerido_adulto, precio_sugerido_nino
                ) VALUES (
                    'abc', 1, 'Test Tour', '', 1,
                    NULL, NULL, 'CAT', '[]',
                    1, '{}',
                    NULL, NULL
                )
                """)
            )
        with sqlite_engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT precio_sugerido_adulto, precio_sugerido_nino"
                    " FROM servicios WHERE id='abc'"
                )
            ).fetchone()
        assert row is not None
        assert row[0] is None
        assert row[1] is None

    def test_upgrade_filas_existentes_sin_cambio(self, sqlite_engine: Engine) -> None:
        """Existing rows keep all other columns unchanged after upgrade."""
        from sqlalchemy import text

        build_servicios_at_0029(sqlite_engine)
        with sqlite_engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO servicios (
                    id, numero, nombre, descripcion, activo,
                    precio_neto_adulto, precio_neto_nino, categoria, horarios,
                    permite_ninos, netos_por_horario
                ) VALUES (
                    'pre', 1, 'Existing Tour', 'desc', 1,
                    100000, 50000, 'PLAYAS', '[]',
                    1, '{}'
                )
                """)
            )
        run_migration_fn(sqlite_engine, _load_migration().upgrade)
        with sqlite_engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT nombre, precio_neto_adulto, precio_sugerido_adulto"
                    " FROM servicios WHERE id='pre'"
                )
            ).fetchone()
        assert row is not None
        assert row[0] == "Existing Tour"
        assert row[1] == 100000
        assert row[2] is None  # new column defaults to NULL


class TestMigration0030Downgrade:
    def test_downgrade_elimina_precio_sugerido_adulto(self, sqlite_engine: Engine) -> None:
        """downgrade() removes precio_sugerido_adulto from servicios."""
        build_servicios_at_0029(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        assert "precio_sugerido_adulto" in table_columns(sqlite_engine, "servicios")
        run_migration_fn(sqlite_engine, migration.downgrade)
        assert "precio_sugerido_adulto" not in table_columns(sqlite_engine, "servicios")

    def test_downgrade_elimina_precio_sugerido_nino(self, sqlite_engine: Engine) -> None:
        """downgrade() removes precio_sugerido_nino from servicios."""
        build_servicios_at_0029(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        assert "precio_sugerido_nino" in table_columns(sqlite_engine, "servicios")
        run_migration_fn(sqlite_engine, migration.downgrade)
        assert "precio_sugerido_nino" not in table_columns(sqlite_engine, "servicios")


class TestMigration0030Chain:
    def test_revision(self) -> None:
        assert _load_migration().revision == "0030"

    def test_down_revision_apunta_a_0029(self) -> None:
        assert _load_migration().down_revision == "0029"
