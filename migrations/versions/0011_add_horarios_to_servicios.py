"""Add horarios column to servicios table.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-14 00:00:00.000000

Adds a JSON column `horarios` (list of canonical "HH:MM" strings) to the
servicios table. All pre-existing rows are backfilled to `[]` via the server
default. Compatible with SQLite (dev) and PostgreSQL (prod).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "servicios",
        sa.Column(
            "horarios",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    # Explicit backfill: guarantee pre-existing rows have [] not NULL on any
    # DB engine that evaluates server_default only at INSERT time, not at ADD COLUMN.
    op.execute("UPDATE servicios SET horarios = '[]' WHERE horarios IS NULL")


def downgrade() -> None:
    op.drop_column("servicios", "horarios")
