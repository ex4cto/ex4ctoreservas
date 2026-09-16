"""add socios_config table

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-15 00:00:00.000000

Partner (socio) configuration: name, percentage share, and optional Telegram ID
for private messages. Primary key is the partner name string.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "socios_config",
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("porcentaje", sa.Numeric(5, 2), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("nombre"),
    )


def downgrade() -> None:
    op.drop_table("socios_config")
