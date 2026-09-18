"""Add netos_por_horario JSON column to servicios table.

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-18 00:00:00.000000

Schema changes:
  - ALTER TABLE servicios ADD COLUMN netos_por_horario JSON NOT NULL DEFAULT '{}'

Data migration (upgrade):
  - UPDATE City Tour Climatizado (nombre = 'CITY TOUR CLIMTIZADO') with morning/afternoon netos

Data migration (downgrade):
  - DROP COLUMN netos_por_horario
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Schema: add netos_por_horario column ---
    op.add_column(
        "servicios",
        sa.Column(
            "netos_por_horario",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )

    conn = op.get_bind()

    # --- Data: seed City Tour Climatizado per-horario netos ---
    # The exact DB name is 'CITY TOUR CLIMTIZADO' (misspelled — matches the real DB record).
    # Values are stored as strings to match the repo string round-trip contract.
    conn.execute(
        sa.text(
            "UPDATE servicios"
            " SET netos_por_horario = '{\"08:00\": \"60000\", \"13:00\": \"55000\"}'"
            " WHERE nombre = 'CITY TOUR CLIMTIZADO'"
        )
    )


def downgrade() -> None:
    op.drop_column("servicios", "netos_por_horario")
