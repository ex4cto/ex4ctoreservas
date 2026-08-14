"""Alembic migration test infrastructure.

Provides a SQLite in-memory engine with Alembic context configured so individual
migration upgrade()/downgrade() functions can be executed in isolation.

Design: rather than running the full Alembic migration chain (which requires all
revisions to be applied in order starting from an empty DB), each migration test
builds the minimum table state required by the revision under test, then runs the
upgrade() / downgrade() callables via a properly configured Alembic MigrationContext.
"""

from __future__ import annotations

from collections.abc import Callable, Generator

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, text


@pytest.fixture()
def sqlite_engine() -> Generator[Engine, None, None]:
    """In-memory SQLite engine for migration tests.

    Uses autocommit=True for the connection to avoid transaction issues when
    DDL statements (like ALTER TABLE / DROP COLUMN) auto-commit on SQLite.
    """
    engine = sa.create_engine("sqlite:///:memory:", echo=False)
    yield engine
    engine.dispose()


def run_migration_fn(engine: Engine, fn: Callable[[], None]) -> None:
    """Execute a migration function (upgrade/downgrade) in an Alembic op context.

    Opens a connection using AUTOCOMMIT isolation so DDL statements don't conflict
    with SQLite's implicit transaction handling. The MigrationContext is configured
    to use this connection.
    """
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            fn()


def table_columns(engine: Engine, table_name: str) -> set[str]:
    """Return the set of column names present in table_name."""
    with engine.connect() as conn:
        inspector = sa.inspect(conn)
        return {col["name"] for col in inspector.get_columns(table_name)}


def build_servicios_at_0010(engine: Engine) -> None:
    """Create the servicios table as it exists at revision 0010 (no horarios column).

    This replicates the schema state before migration 0011 is applied, so the
    upgrade() function can be tested in isolation.
    """
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
                categoria TEXT NOT NULL DEFAULT ''
            )
            """)
        )
