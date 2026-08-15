"""Tests for migration 0013: idempotent seed of transporte categoria.

Test strategy: apply upgrade() directly against a SQLite in-memory connection
that has the categorias_egreso table pre-created (as it exists after the
ff243581ce06 migration). Verifies that:
1. upgrade() inserts a row with nombre="transporte".
2. Calling upgrade() twice does NOT create a duplicate row (idempotent).
3. downgrade() removes the transporte row.

Mirrors the pattern established by test_0012_horarios_venta.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Engine, text

from tests.migraciones.conftest import run_migration_fn

_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "versions"
    / "0013_seed_categoria_transporte.py"
)


def _load_migration() -> ModuleType:
    """Dynamically load the 0013 migration module."""
    if not _MIGRATION_FILE.exists():
        pytest.fail(
            f"Migration file not found: {_MIGRATION_FILE}. "
            "Create migrations/versions/0013_seed_categoria_transporte.py first."
        )
    mod_name = "migration_0013"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _build_categorias_egreso(engine: Engine) -> None:
    """Create categorias_egreso table matching the schema from ff243581ce06."""
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS categorias_egreso (
                nombre TEXT PRIMARY KEY,
                descripcion TEXT NOT NULL,
                activo INTEGER NOT NULL,
                orden INTEGER NOT NULL
            )
            """)
        )


def _count_transporte(engine: Engine) -> int:
    """Return number of rows with nombre='transporte' in categorias_egreso."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM categorias_egreso WHERE nombre = 'transporte'")
        )
        row = result.fetchone()
        return int(row[0]) if row else 0


class TestMigration0013Upgrade:
    def test_upgrade_inserta_fila_transporte(self, sqlite_engine: Engine) -> None:
        """upgrade() inserts a row with nombre='transporte' in categorias_egreso."""
        _build_categorias_egreso(sqlite_engine)
        assert _count_transporte(sqlite_engine) == 0

        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)

        assert _count_transporte(sqlite_engine) == 1

    def test_upgrade_idempotente_sin_duplicado(self, sqlite_engine: Engine) -> None:
        """Calling upgrade() twice does NOT create a duplicate transporte row."""
        _build_categorias_egreso(sqlite_engine)
        migration = _load_migration()

        run_migration_fn(sqlite_engine, migration.upgrade)
        run_migration_fn(sqlite_engine, migration.upgrade)

        assert _count_transporte(sqlite_engine) == 1

    def test_upgrade_fila_tiene_descripcion_correcta(self, sqlite_engine: Engine) -> None:
        """upgrade() seeds the row with descripcion='Transporte (Uber/DiDi)'."""
        _build_categorias_egreso(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)

        with sqlite_engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT descripcion, activo, orden"
                    " FROM categorias_egreso WHERE nombre = 'transporte'"
                )
            ).fetchone()

        assert row is not None
        assert row[0] == "Transporte (Uber/DiDi)"
        assert bool(row[1]) is True
        assert row[2] == 8


class TestMigration0013Downgrade:
    def test_downgrade_elimina_fila_transporte(self, sqlite_engine: Engine) -> None:
        """downgrade() removes the transporte row from categorias_egreso."""
        _build_categorias_egreso(sqlite_engine)
        migration = _load_migration()

        run_migration_fn(sqlite_engine, migration.upgrade)
        assert _count_transporte(sqlite_engine) == 1

        run_migration_fn(sqlite_engine, migration.downgrade)
        assert _count_transporte(sqlite_engine) == 0
