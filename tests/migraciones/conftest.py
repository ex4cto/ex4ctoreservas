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


def build_ventas_at_0011(engine: Engine) -> None:
    """Create the ventas table as it exists at revision 0011 (no horarios_por_servicio column).

    Replicates the schema state before migration 0012 is applied. Column set
    matches VentaModel columns added up through migration 0011:
    id, valor_venta, neto, abono, servicio_ids, cliente_id, tipo_cliente, fecha,
    adultos, ninos, estado, vendedor_nombre, cerrador_nombre, punto_de_venta_id,
    referido_nombre, canal_origen, fechas_por_servicio, vendedor_id, cerrador_id, anulada.
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS ventas (
                id TEXT PRIMARY KEY,
                valor_venta NUMERIC(14,2) NOT NULL,
                neto NUMERIC(14,2) NOT NULL,
                abono NUMERIC(14,2),
                servicio_ids JSON NOT NULL,
                cliente_id TEXT NOT NULL,
                tipo_cliente TEXT NOT NULL,
                fecha DATE NOT NULL,
                adultos INTEGER NOT NULL,
                ninos INTEGER NOT NULL,
                estado TEXT NOT NULL DEFAULT 'PENDIENTE',
                vendedor_nombre TEXT,
                cerrador_nombre TEXT,
                punto_de_venta_id TEXT,
                referido_nombre TEXT,
                canal_origen TEXT,
                fechas_por_servicio JSON,
                vendedor_id TEXT,
                cerrador_id TEXT,
                anulada INTEGER NOT NULL DEFAULT 0
            )
            """)
        )
