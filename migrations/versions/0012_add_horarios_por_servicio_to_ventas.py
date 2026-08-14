"""Add horarios_por_servicio column to ventas table.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-14 00:00:00.000000

Adds a JSON column `horarios_por_servicio` (nullable, no backfill) to the
ventas table. Mirrors 0009 (fechas_por_servicio): nullable=True, no server_default,
no backfill — pre-existing rows legitimately have no time data and stay NULL.
Compatible with SQLite (dev) and PostgreSQL (prod).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ventas", sa.Column("horarios_por_servicio", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ventas", "horarios_por_servicio")
