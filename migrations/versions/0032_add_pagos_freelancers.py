"""Add pagos_freelancers table.

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-08 00:00:00.000000

Records payments made to freelancers for a given commission period.
Supports overlap detection via indexed freelancer_id.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pagos_freelancers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("freelancer_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("desde", sa.Date, nullable=False),
        sa.Column("hasta", sa.Date, nullable=False),
        sa.Column("fecha_pago", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registrado_por_telegram_id", sa.BigInteger, nullable=False),
        sa.Column("registrado_por_nombre", sa.String(200), nullable=True),
    )
    op.create_index(
        "ix_pagos_freelancers_freelancer_id",
        "pagos_freelancers",
        ["freelancer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pagos_freelancers_freelancer_id", table_name="pagos_freelancers")
    op.drop_table("pagos_freelancers")
