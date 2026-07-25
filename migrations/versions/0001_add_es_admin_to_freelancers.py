"""Add es_admin to freelancers table.

Revision ID: 0001
Revises:
Create Date: 2026-07-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "freelancers",
        sa.Column(
            "es_admin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_unique_constraint("uq_freelancers_nombre", "freelancers", ["nombre"])


def downgrade() -> None:
    op.drop_constraint("uq_freelancers_nombre", "freelancers", type_="unique")
    op.drop_column("freelancers", "es_admin")
