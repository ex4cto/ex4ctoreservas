"""Tests for migration 0018: idempotent seed of the remaining egreso categories.

Test strategy mirrors test_0013_seed_transporte.py: apply upgrade() directly
against a SQLite in-memory connection that has the categorias_egreso table
pre-created (as it exists after ff243581ce06). Verifies that:
1. upgrade() inserts the 8 remaining categories.
2. Calling upgrade() twice does NOT create duplicates (idempotent).
3. downgrade() removes the seeded rows.
4. The migration chain links (revision / down_revision) are correct.

'transporte' is intentionally NOT seeded here — it is already seeded by 0013.
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
    / "0018_seed_categorias_egreso.py"
)

_EXPECTED_NOMBRES = {
    "proveedores tour",
    "comisiones",
    "alimentación",
    "marketing",
    "servicios fijos",
    "software",
    "bancarios/impuestos",
    "otro",
}


def _load_migration() -> ModuleType:
    """Dynamically load the 0018 migration module."""
    if not _MIGRATION_FILE.exists():
        pytest.fail(
            f"Migration file not found: {_MIGRATION_FILE}. "
            "Create migrations/versions/0018_seed_categorias_egreso.py first."
        )
    mod_name = "migration_0018"
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


def _nombres(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT nombre FROM categorias_egreso")).fetchall()
    return {row[0] for row in rows}


def _count(engine: Engine) -> int:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT COUNT(*) FROM categorias_egreso")).fetchone()
    return int(row[0]) if row else 0


class TestMigration0018Upgrade:
    def test_upgrade_inserta_las_categorias_esperadas(self, sqlite_engine: Engine) -> None:
        _build_categorias_egreso(sqlite_engine)
        assert _count(sqlite_engine) == 0

        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)

        assert _EXPECTED_NOMBRES.issubset(_nombres(sqlite_engine))

    def test_upgrade_no_siembra_transporte(self, sqlite_engine: Engine) -> None:
        """transporte is owned by migration 0013 — 0018 must not touch it."""
        _build_categorias_egreso(sqlite_engine)
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)

        assert "transporte" not in _nombres(sqlite_engine)

    def test_upgrade_idempotente_sin_duplicados(self, sqlite_engine: Engine) -> None:
        _build_categorias_egreso(sqlite_engine)
        migration = _load_migration()

        run_migration_fn(sqlite_engine, migration.upgrade)
        primero = _count(sqlite_engine)
        run_migration_fn(sqlite_engine, migration.upgrade)
        segundo = _count(sqlite_engine)

        assert primero == segundo == len(_EXPECTED_NOMBRES)

    def test_upgrade_respeta_transporte_preexistente(self, sqlite_engine: Engine) -> None:
        """If transporte already exists (0013 applied), 0018 leaves it untouched."""
        _build_categorias_egreso(sqlite_engine)
        with sqlite_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO categorias_egreso (nombre, descripcion, activo, orden)"
                    " VALUES ('transporte', 'Transporte (Uber/DiDi)', 1, 8)"
                )
            )
        migration = _load_migration()
        run_migration_fn(sqlite_engine, migration.upgrade)

        assert "transporte" in _nombres(sqlite_engine)
        assert _count(sqlite_engine) == len(_EXPECTED_NOMBRES) + 1


class TestMigration0018Downgrade:
    def test_downgrade_elimina_las_sembradas(self, sqlite_engine: Engine) -> None:
        _build_categorias_egreso(sqlite_engine)
        migration = _load_migration()

        run_migration_fn(sqlite_engine, migration.upgrade)
        assert _EXPECTED_NOMBRES.issubset(_nombres(sqlite_engine))

        run_migration_fn(sqlite_engine, migration.downgrade)
        assert _nombres(sqlite_engine).isdisjoint(_EXPECTED_NOMBRES)


class TestMigration0018Chain:
    def test_revision_identifica_la_migracion(self) -> None:
        migration = _load_migration()
        assert migration.revision == "0018_seed_categorias_egreso"

    def test_down_revision_apunta_a_0017(self) -> None:
        migration = _load_migration()
        assert migration.down_revision == "0017"
