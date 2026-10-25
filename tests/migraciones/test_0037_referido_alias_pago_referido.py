"""Tests for migration 0037: rename referido_nombre -> referido_alias,
make porcentaje_referido_maximo nullable, create pago_referido table.

Mirrors the pattern from test_0035_auditoria_entidades.py.
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
    / "0037_referido_alias_pago_referido.py"
)

_EXPECTED_PAGO_REFERIDO_COLS = {
    "id",
    "referido_alias",
    "monto",
    "desde",
    "hasta",
    "fecha_pago",
    "registrado_por_telegram_id",
    "registrado_por_nombre",
}


def _build_ventas_pre_0037(engine: Engine) -> None:
    """Create the ventas table as it exists before migration 0037 (referido_nombre column)."""
    with engine.begin() as conn:
        conn.execute(
            sa.text("""
            CREATE TABLE IF NOT EXISTS ventas (
                id TEXT PRIMARY KEY,
                valor_venta NUMERIC(14,2) NOT NULL,
                neto NUMERIC(14,2) NOT NULL,
                referido_nombre TEXT,
                canal_origen TEXT
            )
            """)
        )


def _build_reglas_pre_0037(engine: Engine) -> None:
    """Create reglas_comision table as it exists before migration 0037."""
    with engine.begin() as conn:
        conn.execute(
            sa.text("""
            CREATE TABLE IF NOT EXISTS reglas_comision (
                id TEXT PRIMARY KEY,
                tipo_cliente TEXT NOT NULL,
                porcentaje_vendedor NUMERIC(5,2) NOT NULL,
                porcentaje_cerrador NUMERIC(5,2) NOT NULL,
                porcentaje_referido_maximo NUMERIC(5,2) NOT NULL
            )
            """)
        )


def _load_migration() -> ModuleType:
    if not _MIGRATION_FILE.exists():
        pytest.fail(f"Migration file not found: {_MIGRATION_FILE}.")
    mod_name = "migration_0037"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMigration0037Upgrade:
    def test_upgrade_renames_referido_nombre_to_referido_alias(
        self, sqlite_engine: Engine
    ) -> None:
        _build_ventas_pre_0037(sqlite_engine)
        _build_reglas_pre_0037(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        cols = table_columns(sqlite_engine, "ventas")
        assert "referido_alias" in cols
        assert "referido_nombre" not in cols

    def test_upgrade_preserves_existing_ventas_data(self, sqlite_engine: Engine) -> None:
        _build_ventas_pre_0037(sqlite_engine)
        _build_reglas_pre_0037(sqlite_engine)
        with sqlite_engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO ventas (id, valor_venta, neto, referido_nombre) "
                    "VALUES ('v1', 100, 90, 'Pepito')"
                )
            )
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        with sqlite_engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT referido_alias FROM ventas WHERE id='v1'")
            ).fetchone()
        assert row is not None
        assert row[0] == "Pepito"

    def test_upgrade_creates_pago_referido_table(self, sqlite_engine: Engine) -> None:
        _build_ventas_pre_0037(sqlite_engine)
        _build_reglas_pre_0037(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        assert "pago_referido" in sa.inspect(sqlite_engine).get_table_names()
        assert table_columns(sqlite_engine, "pago_referido") >= _EXPECTED_PAGO_REFERIDO_COLS

    def test_upgrade_no_rows_lost_in_ventas(self, sqlite_engine: Engine) -> None:
        _build_ventas_pre_0037(sqlite_engine)
        _build_reglas_pre_0037(sqlite_engine)
        with sqlite_engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO ventas (id, valor_venta, neto) VALUES ('v2', 200, 180)"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO ventas (id, valor_venta, neto) VALUES ('v3', 300, 270)"
                )
            )
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        with sqlite_engine.connect() as conn:
            count = conn.execute(sa.text("SELECT COUNT(*) FROM ventas")).scalar()
        assert count == 2


class TestMigration0037Downgrade:
    def test_downgrade_renames_back_to_referido_nombre(self, sqlite_engine: Engine) -> None:
        _build_ventas_pre_0037(sqlite_engine)
        _build_reglas_pre_0037(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        run_migration_fn(sqlite_engine, migration.downgrade)
        cols = table_columns(sqlite_engine, "ventas")
        assert "referido_nombre" in cols
        assert "referido_alias" not in cols

    def test_downgrade_drops_pago_referido_table(self, sqlite_engine: Engine) -> None:
        _build_ventas_pre_0037(sqlite_engine)
        _build_reglas_pre_0037(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        run_migration_fn(sqlite_engine, migration.downgrade)
        assert "pago_referido" not in sa.inspect(sqlite_engine).get_table_names()


class TestMigration0037Chain:
    def test_revision(self) -> None:
        assert _load_migration().revision == "0037"

    def test_down_revision_apunta_a_0036(self) -> None:
        assert _load_migration().down_revision == "0036"
