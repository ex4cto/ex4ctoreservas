"""add pagos_socios table

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-15 00:00:00.000000

Manual partner payment records (liquidaciones). Tracks who was paid, how much,
when, whether it was a full or partial payment, and an optional note.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import garay.infraestructura.persistencia.tipos

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pagos_socios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre_socio", sa.String(), nullable=False),
        sa.Column(
            "monto",
            garay.infraestructura.persistencia.tipos.TipoDinero(),
            nullable=False,
        ),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("registrado_en", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("pagos_socios")
