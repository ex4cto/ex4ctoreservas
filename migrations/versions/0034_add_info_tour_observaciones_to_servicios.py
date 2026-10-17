"""Add info_tour and observaciones columns to servicios table.

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-17 00:00:00.000000

Adds two nullable TEXT content fields to the servicios table so that tour
itinerary details and restriction notes can be stored per service and
forwarded to participating freelancers after a sale is registered.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("servicios", sa.Column("info_tour", sa.Text(), nullable=True))
    op.add_column("servicios", sa.Column("observaciones", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("servicios", "observaciones")
    op.drop_column("servicios", "info_tour")
