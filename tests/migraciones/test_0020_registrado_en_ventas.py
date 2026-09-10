"""Tests for migration 0020: add registrado_en column to ventas."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Engine

from tests.migraciones.conftest import (
    build_ventas_at_0011,
    run_migration_fn,
    table_columns,
)

_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "versions"
    / "0020_add_registrado_en_to_ventas.py"
)


def _load_migration() -> ModuleType:
    if not _MIGRATION_FILE.exists():
        pytest.fail(f"Migration file not found: {_MIGRATION_FILE}.")
    mod_name = "migration_0020"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMigration0020Upgrade:
    def test_upgrade_agrega_columna(self, sqlite_engine: Engine) -> None:
        build_ventas_at_0011(sqlite_engine)
        assert "registrado_en" not in table_columns(sqlite_engine, "ventas")
        run_migration_fn(sqlite_engine, _load_migration().upgrade)
        assert "registrado_en" in table_columns(sqlite_engine, "ventas")


class TestMigration0020Downgrade:
    def test_downgrade_elimina_columna(self, sqlite_engine: Engine) -> None:
        build_ventas_at_0011(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        run_migration_fn(sqlite_engine, migration.downgrade)
        assert "registrado_en" not in table_columns(sqlite_engine, "ventas")


class TestMigration0020Chain:
    def test_revision(self) -> None:
        assert _load_migration().revision == "0020"

    def test_down_revision_apunta_a_0019(self) -> None:
        assert _load_migration().down_revision == "0019_auditoria_egresos"
