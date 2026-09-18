"""add metodo_pago to ventas

Revision ID: e5f6a7b8c9d0
Revises: ff243581ce06
Create Date: 2026-09-18

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "ff243581ce06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ventas", sa.Column("metodo_pago", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("ventas", "metodo_pago")
