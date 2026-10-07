"""Add contadores_documento table.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-07 00:00:00.000000

Generic counter table for consecutively numbered documents (e.g. cuentas de cobro).
Each row tracks the last assigned number for a named document type.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contadores_documento",
        sa.Column("tipo", sa.String(100), primary_key=True),
        sa.Column("ultimo_numero", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("contadores_documento")
