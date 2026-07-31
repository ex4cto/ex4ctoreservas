"""Add categoria to servicios table.

Revision ID: 0003
Revises: d4e5f6a7b8c9
Create Date: 2026-07-31
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "servicios",
        sa.Column("categoria", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("servicios", "categoria")
