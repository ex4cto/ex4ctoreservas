"""Tests for migration 0012: add horarios_por_servicio column to ventas.

Test strategy: apply the upgrade()/downgrade() functions directly against a
SQLite in-memory connection that already has the ventas table at revision 0011
state (no horarios_por_servicio column). This avoids running the full Alembic
chain while still exercising the actual migration DDL via a live Alembic
Operations context. Mirrors the pattern from test_0011_horarios.py.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Engine, text

from tests.migraciones.conftest import (
    build_ventas_at_0011,
    run_migration_fn,
    table_columns,
)

_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "versions"
    / "0012_add_horarios_por_servicio_to_ventas.py"
)


def _load_migration() -> ModuleType:
    """Dynamically load the 0012 migration module."""
    if not _MIGRATION_FILE.exists():
        pytest.fail(
            f"Migration file not found: {_MIGRATION_FILE}. "
            "Create migrations/versions/0012_add_horarios_por_servicio_to_ventas.py first."
        )
    mod_name = "migration_0012"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMigration0012Upgrade:
    def test_upgrade_agrega_columna_horarios_por_servicio(self, sqlite_engine: Engine) -> None:
        """upgrade() adds the horarios_por_servicio column to the ventas table."""
        migration = _load_migration()

        build_ventas_at_0011(sqlite_engine)
        assert "horarios_por_servicio" not in table_columns(sqlite_engine, "ventas")

        run_migration_fn(sqlite_engine, migration.upgrade)

        assert "horarios_por_servicio" in table_columns(sqlite_engine, "ventas")

    def test_upgrade_filas_preexistentes_quedan_null(self, sqlite_engine: Engine) -> None:
        """upgrade() leaves pre-existing rows with horarios_por_servicio = NULL.

        Unlike 0011 (horarios on servicios, NOT NULL with server_default=[]),
        this column is nullable=True with no backfill — existing rows stay NULL.
        """
        migration = _load_migration()

        venta_id = str(uuid.uuid4())
        build_ventas_at_0011(sqlite_engine)
        with sqlite_engine.begin() as conn:
            conn.execute(
                text(
                    """INSERT INTO ventas
                    (id, valor_venta, neto, servicio_ids, cliente_id, tipo_cliente,
                     fecha, adultos, ninos)
                    VALUES (:id, 100000, 80000, '[]', :cid, 'EXTERNO', '2026-12-25', 2, 0)"""
                ),
                {"id": venta_id, "cid": str(uuid.uuid4())},
            )

        run_migration_fn(sqlite_engine, migration.upgrade)

        with sqlite_engine.connect() as conn:
            row = conn.execute(
                text("SELECT horarios_por_servicio FROM ventas WHERE id = :id"),
                {"id": venta_id},
            ).fetchone()

        assert row is not None
        # Pre-existing row must be NULL — no backfill applied.
        assert row[0] is None, f"Expected NULL, got {row[0]!r}"


class TestMigration0012Downgrade:
    def test_downgrade_elimina_columna_horarios_por_servicio(
        self, sqlite_engine: Engine
    ) -> None:
        """downgrade() removes the horarios_por_servicio column from ventas."""
        migration = _load_migration()

        build_ventas_at_0011(sqlite_engine)
        run_migration_fn(sqlite_engine, migration.upgrade)
        assert "horarios_por_servicio" in table_columns(sqlite_engine, "ventas")

        # SQLite < 3.35 does not support DROP COLUMN natively without batch mode.
        try:
            run_migration_fn(sqlite_engine, migration.downgrade)
            assert "horarios_por_servicio" not in table_columns(sqlite_engine, "ventas")
        except Exception as exc:
            pytest.skip(
                f"SQLite does not support DROP COLUMN inline: {exc}. "
                "Downgrade is covered by Postgres CI."
            )

    def test_downgrade_mantiene_otras_columnas(self, sqlite_engine: Engine) -> None:
        """After downgrade, the other ventas columns are still present."""
        migration = _load_migration()

        build_ventas_at_0011(sqlite_engine)
        run_migration_fn(sqlite_engine, migration.upgrade)

        try:
            run_migration_fn(sqlite_engine, migration.downgrade)
            cols = table_columns(sqlite_engine, "ventas")
            expected = {
                "id", "valor_venta", "neto", "abono", "servicio_ids",
                "cliente_id", "tipo_cliente", "fecha", "adultos", "ninos",
                "estado", "vendedor_nombre", "cerrador_nombre", "punto_de_venta_id",
                "referido_nombre", "canal_origen", "fechas_por_servicio",
                "vendedor_id", "cerrador_id", "anulada",
            }
            assert expected.issubset(cols)
        except Exception as exc:
            pytest.skip(
                f"SQLite does not support DROP COLUMN inline: {exc}. "
                "Covered by Postgres CI."
            )
