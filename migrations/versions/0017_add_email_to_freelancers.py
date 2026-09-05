"""add email to freelancers

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-04 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "freelancers",
        sa.Column("email", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("freelancers", "email")
