"""Add cambios_imagen_pendiente table.

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-14 00:00:00.000000

Tracks pending catalog image changes so the 5-minute reminder and
/actualizar_imagenes handler have a durable record of what changed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cambios_imagen_pendiente",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("descripcion", sa.String(1000), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("cambios_imagen_pendiente")
