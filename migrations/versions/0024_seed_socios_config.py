"""seed initial socios_config rows

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-16 00:00:00.000000

Inserts the three initial partner configurations (empresa 50%, garay 25%,
ryan 25%) with no telegram_id. ON CONFLICT DO NOTHING makes this idempotent.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOCIOS_INICIALES = [
    {"nombre": "empresa", "porcentaje": "50", "telegram_id": None},
    {"nombre": "garay", "porcentaje": "25", "telegram_id": None},
    {"nombre": "ryan", "porcentaje": "25", "telegram_id": None},
]


def upgrade() -> None:
    conn = op.get_bind()
    for socio in _SOCIOS_INICIALES:
        conn.execute(
            sa.text(
                "INSERT INTO socios_config (nombre, porcentaje, telegram_id) "
                "VALUES (:nombre, :porcentaje, :telegram_id) "
                "ON CONFLICT (nombre) DO NOTHING"
            ),
            socio,
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM socios_config WHERE nombre IN ('empresa', 'garay', 'ryan')"
        )
    )
