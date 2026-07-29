"""add score, confianza and unique constraint to conciliaciones

Revision ID: a1b2c3d4e5f6
Revises: ff243581ce06
Create Date: 2026-07-28 22:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "ff243581ce06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conciliaciones",
        sa.Column("score", sa.Numeric(precision=5, scale=4), nullable=True),
    )
    op.add_column(
        "conciliaciones",
        sa.Column("confianza", sa.Numeric(precision=5, scale=4), nullable=True),
    )
    op.create_unique_constraint(
        "uq_conciliaciones_ingreso_id", "conciliaciones", ["ingreso_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_conciliaciones_ingreso_id", "conciliaciones", type_="unique")
    op.drop_column("conciliaciones", "confianza")
    op.drop_column("conciliaciones", "score")
