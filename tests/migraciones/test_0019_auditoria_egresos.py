"""Tests for migration 0019: create auditoria_egresos table.

Mirrors the pattern of the other migration tests: load the module and run
upgrade()/downgrade() against an in-memory SQLite engine in isolation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from sqlalchemy import Engine

from tests.migraciones.conftest import run_migration_fn, table_columns

_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "versions"
    / "0019_auditoria_egresos.py"
)

_EXPECTED_COLS = {
    "id",
    "egreso_id",
    "campo",
    "valor_anterior",
    "valor_nuevo",
    "realizada_por_telegram_id",
    "realizada_por_nombre",
    "realizada_at",
}


def _load_migration() -> ModuleType:
    if not _MIGRATION_FILE.exists():
        pytest.fail(f"Migration file not found: {_MIGRATION_FILE}.")
    mod_name = "migration_0019"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMigration0019Upgrade:
    def test_upgrade_crea_tabla_con_columnas(self, sqlite_engine: Engine) -> None:
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        assert table_columns(sqlite_engine, "auditoria_egresos") >= _EXPECTED_COLS


class TestMigration0019Downgrade:
    def test_downgrade_elimina_tabla(self, sqlite_engine: Engine) -> None:
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        run_migration_fn(sqlite_engine, migration.downgrade)
        assert "auditoria_egresos" not in sa.inspect(sqlite_engine).get_table_names()


class TestMigration0019Chain:
    def test_revision(self) -> None:
        assert _load_migration().revision == "0019_auditoria_egresos"

    def test_down_revision_apunta_a_0018(self) -> None:
        assert _load_migration().down_revision == "0018_seed_categorias_egreso"
