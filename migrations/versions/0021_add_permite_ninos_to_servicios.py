"""add permite_ninos to servicios

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-10 00:00:00.000000

Whether a service accepts children at all. Some tours do not admit children
("NO INGRESAN NIÑOS"); this flag lets the sale flow skip the children prompt.
Not-null with a server_default of true: pre-existing services keep admitting
children (the common case).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "servicios",
        sa.Column(
            "permite_ninos",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("servicios", "permite_ninos")
