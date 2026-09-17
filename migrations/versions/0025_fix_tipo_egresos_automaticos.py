"""Fix tipo=manual in old automatic egresos

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-16 00:00:00.000000

When the `tipo` column was added to the `egresos` table the column default
("manual") was applied to every existing row, including rows that were
created by the webhook/email parser and should have tipo="automatico".

Reliable signal: webhook-originated rows always carry a non-null `referencia`
(idempotency key) or a non-null `correo_origen` (sender email). Manual egresos
have both fields as NULL.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE egresos "
            "SET tipo = 'automatico' "
            "WHERE tipo = 'manual' "
            "  AND (referencia IS NOT NULL OR correo_origen IS NOT NULL)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE egresos "
            "SET tipo = 'manual' "
            "WHERE tipo = 'automatico' "
            "  AND (referencia IS NOT NULL OR correo_origen IS NOT NULL)"
        )
    )
