"""create auditoria_egresos table

Revision ID: 0019_auditoria_egresos
Revises: 0018_seed_categorias_egreso
Create Date: 2026-09-10 00:00:00.000000

Per-field audit trail for manual egreso edits (item C). One row per field changed.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_auditoria_egresos"
down_revision: Union[str, None] = "0018_seed_categorias_egreso"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auditoria_egresos",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "egreso_id", sa.Uuid(as_uuid=True), sa.ForeignKey("egresos.id"), nullable=False
        ),
        sa.Column("campo", sa.String(), nullable=False),
        sa.Column("valor_anterior", sa.Text(), nullable=False),
        sa.Column("valor_nuevo", sa.Text(), nullable=False),
        sa.Column("realizada_por_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("realizada_por_nombre", sa.String(), nullable=True),
        sa.Column("realizada_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("auditoria_egresos")
