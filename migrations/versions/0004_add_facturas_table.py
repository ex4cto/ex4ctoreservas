"""Add facturas table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-31
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "facturas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("numero", sa.String(), nullable=False),
        sa.Column("venta_id", sa.Uuid(), nullable=False),
        sa.Column("cliente_nombre", sa.String(), nullable=True),
        sa.Column("cliente_email", sa.String(), nullable=False),
        sa.Column("monto_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("abono", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("html_contenido", sa.Text(), nullable=False),
        sa.Column("estado_envio", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["venta_id"], ["ventas.id"]),
        sa.UniqueConstraint("venta_id", name="uq_facturas_venta_id"),
    )


def downgrade() -> None:
    op.drop_table("facturas")
