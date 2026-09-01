"""add factura_idioma to ventas

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-31 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ventas",
        sa.Column(
            "factura_idioma",
            sa.String(),
            nullable=False,
            server_default="es",
        ),
    )


def downgrade() -> None:
    op.drop_column("ventas", "factura_idioma")
