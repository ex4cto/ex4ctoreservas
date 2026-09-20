"""set telegram_id for socio empresa (Sharimel)

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-19 00:00:00.000000

Data migration: sets the Telegram user ID for the 'empresa' socio so she
receives per-sale DM notifications from /resumen_divisiones and tiquetera.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMPRESA_TELEGRAM_ID = 8710698734


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE socios_config SET telegram_id = :tid WHERE nombre = 'empresa'"
        ),
        {"tid": _EMPRESA_TELEGRAM_ID},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE socios_config SET telegram_id = NULL WHERE nombre = 'empresa'"
        )
    )
