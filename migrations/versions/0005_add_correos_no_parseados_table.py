"""Add correos_no_parseados table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "correos_no_parseados",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("banco", sa.String(), nullable=False),
        sa.Column("direccion", sa.String(), nullable=False),
        sa.Column("referencia", sa.String(), nullable=False),
        sa.Column("asunto", sa.String(), nullable=False),
        sa.Column("correo_origen", sa.String(), nullable=True),
        sa.Column("cuerpo_texto", sa.Text(), nullable=False),
        sa.Column("cuerpo_html", sa.Text(), nullable=False),
        sa.Column("error_parseo", sa.String(), nullable=False),
        sa.Column("fecha_recibido", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "procesado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "intentos",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error_ultimo", sa.String(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referencia", name="uq_correos_no_parseados_referencia"),
    )


def downgrade() -> None:
    op.drop_table("correos_no_parseados")
