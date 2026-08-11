"""add anulada to ventas and auditoria_ventas table

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-11 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ventas",
        sa.Column(
            "anulada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_table(
        "auditoria_ventas",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("venta_id", sa.Uuid(as_uuid=True), sa.ForeignKey("ventas.id"), nullable=False),
        sa.Column("accion", sa.String(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("realizada_por_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("realizada_por_nombre", sa.String(), nullable=True),
        sa.Column("realizada_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("datos_previos", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("auditoria_ventas")
    op.drop_column("ventas", "anulada")
