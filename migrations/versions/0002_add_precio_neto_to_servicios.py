"""Add precio_neto_adulto and precio_neto_nino to servicios table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "servicios",
        sa.Column("precio_neto_adulto", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "servicios",
        sa.Column("precio_neto_nino", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("servicios", "precio_neto_nino")
    op.drop_column("servicios", "precio_neto_adulto")
