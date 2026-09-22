"""Tests for migration 0029: add mensaje_grupo_id column to ventas."""

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
    / "0029_add_mensaje_grupo_id_to_ventas.py"
)


def _load_migration() -> ModuleType:
    if not _MIGRATION_FILE.exists():
        pytest.fail(f"Migration file not found: {_MIGRATION_FILE}.")
    mod_name = "migration_0029"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMigration0029Upgrade:
    def test_upgrade_agrega_columna_nullable(self, sqlite_engine: Engine) -> None:
        """upgrade() adds a nullable mensaje_grupo_id column to ventas."""
        build_ventas_at_0011(sqlite_engine)
        assert "mensaje_grupo_id" not in table_columns(sqlite_engine, "ventas")
        run_migration_fn(sqlite_engine, _load_migration().upgrade)
        assert "mensaje_grupo_id" in table_columns(sqlite_engine, "ventas")

    def test_upgrade_columna_acepta_null(self, sqlite_engine: Engine) -> None:
        """After upgrade, inserting a row with NULL mensaje_grupo_id succeeds."""
        from sqlalchemy import text

        build_ventas_at_0011(sqlite_engine)
        run_migration_fn(sqlite_engine, _load_migration().upgrade)
        with sqlite_engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO ventas (
                    id, valor_venta, neto, abono, servicio_ids, cliente_id,
                    tipo_cliente, fecha, adultos, ninos, estado,
                    vendedor_nombre, cerrador_nombre, punto_de_venta_id,
                    referido_nombre, canal_origen, fechas_por_servicio,
                    vendedor_id, cerrador_id, anulada, mensaje_grupo_id
                ) VALUES (
                    'abc', 100, 80, NULL, '[]', 'cli1',
                    'EXTERNO', '2026-01-01', 1, 0, 'PENDIENTE',
                    NULL, NULL, NULL,
                    NULL, NULL, NULL,
                    NULL, NULL, 0, NULL
                )
                """)
            )
        with sqlite_engine.connect() as conn:
            row = conn.execute(
                text("SELECT mensaje_grupo_id FROM ventas WHERE id='abc'")
            ).fetchone()
        assert row is not None
        assert row[0] is None


class TestMigration0029Downgrade:
    def test_downgrade_elimina_columna(self, sqlite_engine: Engine) -> None:
        """downgrade() removes the mensaje_grupo_id column from ventas."""
        build_ventas_at_0011(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)
        assert "mensaje_grupo_id" in table_columns(sqlite_engine, "ventas")
        run_migration_fn(sqlite_engine, migration.downgrade)
        assert "mensaje_grupo_id" not in table_columns(sqlite_engine, "ventas")


class TestMigration0029Chain:
    def test_revision(self) -> None:
        assert _load_migration().revision == "0029"

    def test_down_revision_apunta_a_0028(self) -> None:
        assert _load_migration().down_revision == "0028"
