"""add email and identificacion to clientes

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clientes", sa.Column("email", sa.String(), nullable=True))
    op.add_column("clientes", sa.Column("identificacion", sa.String(), nullable=True))
    op.add_column("clientes", sa.Column("tipo_identificacion", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("clientes", "tipo_identificacion")
    op.drop_column("clientes", "identificacion")
    op.drop_column("clientes", "email")
