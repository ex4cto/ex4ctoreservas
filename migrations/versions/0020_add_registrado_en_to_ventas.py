"""add registrado_en to ventas

Revision ID: 0020
Revises: 0019_auditoria_egresos
Create Date: 2026-09-10 00:00:00.000000

UTC timestamp of when a sale was registered in the system (not the tour date).
Enables managing sales by registration recency. Nullable: sales predating this
feature stay NULL.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019_auditoria_egresos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ventas",
        sa.Column(
            "registrado_en",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("ventas", "registrado_en")
