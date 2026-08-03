"""Add freelancer identity columns and swap uniqueness constraint.

Adds nombre_completo, cedula, and display as nullable columns.
Drops uq_freelancers_nombre (nombre no longer unique after homonym support).
Creates uq_freelancers_cedula (cedula unique, NULL-safe in Postgres).

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("freelancers", sa.Column("nombre_completo", sa.String(), nullable=True))
    op.add_column("freelancers", sa.Column("cedula", sa.String(), nullable=True))
    op.add_column("freelancers", sa.Column("display", sa.String(), nullable=True))
    op.drop_constraint("uq_freelancers_nombre", "freelancers", type_="unique")
    op.create_unique_constraint("uq_freelancers_cedula", "freelancers", ["cedula"])


def downgrade() -> None:
    op.drop_constraint("uq_freelancers_cedula", "freelancers", type_="unique")
    op.create_unique_constraint("uq_freelancers_nombre", "freelancers", ["nombre"])
    op.drop_column("freelancers", "display")
    op.drop_column("freelancers", "cedula")
    op.drop_column("freelancers", "nombre_completo")
