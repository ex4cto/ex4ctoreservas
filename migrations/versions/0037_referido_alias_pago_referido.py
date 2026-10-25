"""Rename referido_nombre to referido_alias, make porcentaje_referido_maximo nullable,
and create pago_referido table.

Revision ID: 0037
Revises: 0036
Create Date: 2026-10-25 00:00:00.000000

Changes:
- ventas.referido_nombre -> ventas.referido_alias (column rename)
- reglas_comision.porcentaje_referido_maximo: DROP NOT NULL (make nullable)
- CREATE TABLE pago_referido: records freelancer-referido payment events
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Rename referido_nombre -> referido_alias on ventas
    with op.batch_alter_table("ventas") as batch_op:
        batch_op.alter_column(
            "referido_nombre",
            new_column_name="referido_alias",
        )

    # 2. Make porcentaje_referido_maximo nullable on reglas_comision
    with op.batch_alter_table("reglas_comision") as batch_op:
        batch_op.alter_column(
            "porcentaje_referido_maximo",
            existing_type=sa.Numeric(5, 2),
            nullable=True,
        )

    # 3. Create pago_referido table
    op.create_table(
        "pago_referido",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("referido_alias", sa.String(), nullable=False),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=False),
        sa.Column("fecha_pago", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registrado_por_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("registrado_por_nombre", sa.String(), nullable=True),
    )


def downgrade() -> None:
    # 3. Drop pago_referido table
    op.drop_table("pago_referido")

    # 2. Restore NOT NULL on porcentaje_referido_maximo
    with op.batch_alter_table("reglas_comision") as batch_op:
        batch_op.alter_column(
            "porcentaje_referido_maximo",
            existing_type=sa.Numeric(5, 2),
            nullable=False,
        )

    # 1. Rename referido_alias -> referido_nombre on ventas
    with op.batch_alter_table("ventas") as batch_op:
        batch_op.alter_column(
            "referido_alias",
            new_column_name="referido_nombre",
        )
