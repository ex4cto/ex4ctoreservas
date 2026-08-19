"""Add destinatario column to egresos table.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-19 00:00:00.000000

Adds a nullable String column `destinatario` to `egresos` that stores the
payee/recipient extracted from bank notification emails (name, masked account
number, or merchant name). NULL for manual egresos and non-payee email formats
(Uber/DiDi, Pago factura Nequi) and all legacy rows (backfill is a separate script).

Targets PostgreSQL (the production migration database). Dev/test schemas are built
via SQLAlchemy metadata `create_all`, not through this migration chain.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "egresos",
        sa.Column("destinatario", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("egresos", "destinatario")
