"""add precio_sugerido_adulto and precio_sugerido_nino to servicios

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-01 00:00:00.000000

Adds two nullable NUMERIC(14,2) columns to servicios for the suggested public
price displayed on price lists. No server_default; existing rows are NULL.
Reversible: downgrade drops both columns.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "servicios",
        sa.Column("precio_sugerido_adulto", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "servicios",
        sa.Column("precio_sugerido_nino", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("servicios", "precio_sugerido_nino")
    op.drop_column("servicios", "precio_sugerido_adulto")
