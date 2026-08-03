"""Add vendedor_id and cerrador_id FK columns to ventas.

Nullable FK columns linking ventas to freelancers.id, tracking which
registered freelancer acted as vendor and/or closer for each sale.
Historical rows (pre-Slice-B) keep NULL in both columns.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "ventas",
        sa.Column("vendedor_id", sa.Uuid(), sa.ForeignKey("freelancers.id"), nullable=True),
    )
    op.add_column(
        "ventas",
        sa.Column("cerrador_id", sa.Uuid(), sa.ForeignKey("freelancers.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ventas", "cerrador_id")
    op.drop_column("ventas", "vendedor_id")
