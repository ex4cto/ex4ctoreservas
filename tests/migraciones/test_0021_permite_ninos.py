"""Tests for migration 0021: add permite_ninos column to servicios."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Engine, text

from tests.migraciones.conftest import (
    build_servicios_at_0020,
    run_migration_fn,
    table_columns,
)

_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "versions"
    / "0021_add_permite_ninos_to_servicios.py"
)


def _load_migration() -> ModuleType:
    if not _MIGRATION_FILE.exists():
        pytest.fail(f"Migration file not found: {_MIGRATION_FILE}.")
    mod_name = "migration_0021"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMigration0021Upgrade:
    def test_upgrade_agrega_columna(self, sqlite_engine: Engine) -> None:
        build_servicios_at_0020(sqlite_engine)
        assert "permite_ninos" not in table_columns(sqlite_engine, "servicios")
        run_migration_fn(sqlite_engine, _load_migration().upgrade)
        assert "permite_ninos" in table_columns(sqlite_engine, "servicios")

    def test_upgrade_filas_preexistentes_quedan_true(self, sqlite_engine: Engine) -> None:
        build_servicios_at_0020(sqlite_engine)
        with sqlite_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO servicios (id, numero, nombre) VALUES ('s1', 1, 'Tour')"
                )
            )
        run_migration_fn(sqlite_engine, _load_migration().upgrade)
        with sqlite_engine.connect() as conn:
            valor = conn.execute(
                text("SELECT permite_ninos FROM servicios WHERE id = 's1'")
            ).scalar_one()
        assert bool(valor) is True


class TestMigration0021Downgrade:
    def test_downgrade_elimina_columna(self, sqlite_engine: Engine) -> None:
        build_servicios_at_0020(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        run_migration_fn(sqlite_engine, migration.downgrade)
        assert "permite_ninos" not in table_columns(sqlite_engine, "servicios")


class TestMigration0021Chain:
    def test_revision(self) -> None:
        assert _load_migration().revision == "0021"

    def test_down_revision_apunta_a_0020(self) -> None:
        assert _load_migration().down_revision == "0020"
