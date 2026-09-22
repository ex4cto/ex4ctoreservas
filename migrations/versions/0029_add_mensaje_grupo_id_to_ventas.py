"""add mensaje_grupo_id to ventas

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-22 00:00:00.000000

Adds a nullable BIGINT column mensaje_grupo_id to ventas so the registration
handler can persist the Telegram group message_id returned when a sale is
announced. Legacy rows remain NULL and degrade gracefully.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ventas",
        sa.Column("mensaje_grupo_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ventas", "mensaje_grupo_id")
