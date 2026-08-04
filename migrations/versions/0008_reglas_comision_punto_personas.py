"""Add punto_de_venta_nombre and numero_personas to reglas_comision.

Replaces the anonymous unique constraint on tipo_cliente with a composite
unique on (tipo_cliente, punto_de_venta_nombre, numero_personas) to support
point-specific commission rules (e.g., Crespo with 1 or 2 persons).

Pre-check (S6): aborts if any existing DIGITAL venta has a punto_de_venta_id,
as the DigitalConPuntoDeVenta domain invariant would be violated for such rows.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-03

Validation notes (manual / CI):
  - Run `alembic upgrade head` against SQLite dev DB: verify reaches 0008.
  - Run `alembic downgrade 0007`: verify rollback removes columns and restores.
  - In Postgres, batch_alter_table degrades to direct ALTER; the anonymous
    unique on tipo_cliente (from 0000_initial_schema) is dropped by
    recreate='always' which rebuilds the table from the current model state.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # S6: pre-check — fail loudly if any DIGITAL venta has a punto_de_venta_id.
    # This ensures the DigitalConPuntoDeVenta domain invariant is safe to enable.
    conn = op.get_bind()
    n: int = conn.execute(
        sa.text(
            "SELECT count(*) FROM ventas "
            "WHERE tipo_cliente = 'DIGITAL' AND punto_de_venta_id IS NOT NULL"
        )
    ).scalar() or 0
    if n:
        raise RuntimeError(
            f"{n} venta(s) DIGITAL with punto_de_venta_id found. "
            "Clean up these rows before running migration 0008."
        )

    # batch_alter_table with recreate='always' rebuilds the table from the current
    # ORM model state, dropping the anonymous unique(tipo_cliente) from 0000 without
    # needing to name it, and adding the new composite unique constraint.
    with op.batch_alter_table("reglas_comision", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("punto_de_venta_nombre", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("numero_personas", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_reglas_tipo_punto_personas",
            ["tipo_cliente", "punto_de_venta_nombre", "numero_personas"],
        )


def downgrade() -> None:
    # Reverse: drop the 2 new columns and the composite unique, restore the
    # anonymous unique on tipo_cliente alone.
    with op.batch_alter_table("reglas_comision", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_reglas_tipo_punto_personas", type_="unique")
        batch_op.drop_column("punto_de_venta_nombre")
        batch_op.drop_column("numero_personas")
        batch_op.create_unique_constraint(None, ["tipo_cliente"])
