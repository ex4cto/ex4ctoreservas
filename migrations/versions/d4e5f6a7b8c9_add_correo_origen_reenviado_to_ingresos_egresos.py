"""add correo_origen and reenviado to ingresos and egresos

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-30 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingresos",
        sa.Column("correo_origen", sa.String(), nullable=True),
    )
    op.add_column(
        "ingresos",
        sa.Column(
            "reenviado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "egresos",
        sa.Column("correo_origen", sa.String(), nullable=True),
    )
    op.add_column(
        "egresos",
        sa.Column(
            "reenviado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("egresos", "reenviado")
    op.drop_column("egresos", "correo_origen")
    op.drop_column("ingresos", "reenviado")
    op.drop_column("ingresos", "correo_origen")
