"""Add contactos_reserva JSON column to servicios table.

Revision ID: 0036
Revises: 0035
Create Date: 2026-10-22 00:00:00.000000

Stores an ordered list of operator contacts per tour (up to 4), each with
a name and a number (phone or Telegram group name). Used to populate the
contact DM sent to admins on every new sale.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "servicios",
        sa.Column(
            "contactos_reserva",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("servicios", "contactos_reserva")
