"""Add gasto_recurrente_id column to egresos table.

Revision ID: 0014
Revises: 0013_seed_categoria_transporte
Create Date: 2026-08-18 00:00:00.000000

Adds a nullable UUID FK column `gasto_recurrente_id` to `egresos` that references
`gastos_recurrentes.id`. Pre-existing rows are unaffected (column is NULL by default).
Targets PostgreSQL (the production migration database). Dev/test schemas are built
via SQLAlchemy metadata `create_all`, not through this migration chain.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013_seed_categoria_transporte"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "egresos",
        sa.Column(
            "gasto_recurrente_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("gastos_recurrentes.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("egresos", "gasto_recurrente_id")
