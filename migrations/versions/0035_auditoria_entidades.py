"""Create auditoria_entidades table.

Revision ID: 0035
Revises: 0034
Create Date: 2026-10-17 00:00:00.000000

Generic per-field audit trail for the five money-affecting entities
(servicios, freelancers, reglas_comision, socios_config, puntos_de_venta).
One row per changed field; identity is (entidad_tipo, entidad_id) or
(entidad_tipo, entidad_clave) for text-keyed entities like socios_config.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auditoria_entidades",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("entidad_tipo", sa.String(), nullable=False),
        sa.Column("entidad_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("entidad_clave", sa.String(), nullable=True),
        sa.Column("campo", sa.String(), nullable=False),
        sa.Column("valor_anterior", sa.Text(), nullable=True),
        sa.Column("valor_nuevo", sa.Text(), nullable=True),
        sa.Column("realizada_por_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("realizada_por_nombre", sa.String(), nullable=True),
        sa.Column("realizada_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_auditoria_entidades_tipo_id",
        "auditoria_entidades",
        ["entidad_tipo", "entidad_id"],
    )
    op.create_index(
        "ix_auditoria_entidades_realizada_at",
        "auditoria_entidades",
        ["realizada_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auditoria_entidades_realizada_at", table_name="auditoria_entidades")
    op.drop_index("ix_auditoria_entidades_tipo_id", table_name="auditoria_entidades")
    op.drop_table("auditoria_entidades")
