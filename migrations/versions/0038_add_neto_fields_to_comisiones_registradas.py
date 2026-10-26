"""Add neto_vendedor and neto_cerrador to comisiones_registradas.

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-25 00:00:00.000000

Changes:
- comisiones_registradas.neto_vendedor: nullable Numeric(14,2) (NULL for pre-PR2 rows)
- comisiones_registradas.neto_cerrador: nullable Numeric(14,2) (NULL for pre-PR2 rows)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("comisiones_registradas") as batch_op:
        batch_op.add_column(
            sa.Column("neto_vendedor", sa.Numeric(14, 2), nullable=True)
        )
        batch_op.add_column(
            sa.Column("neto_cerrador", sa.Numeric(14, 2), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("comisiones_registradas") as batch_op:
        batch_op.drop_column("neto_cerrador")
        batch_op.drop_column("neto_vendedor")
