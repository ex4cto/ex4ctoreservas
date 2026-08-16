"""Seed the transporte expense category row.

Revision ID: 0013_seed_categoria_transporte
Revises: 0012
Create Date: 2026-08-15 00:00:00.000000

Inserts the 'transporte' row into categorias_egreso.
Idempotent: checks for existence before inserting so re-running alembic upgrade
head on an already-migrated database is safe.
downgrade() deletes the transporte row.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from garay.dominio.conciliacion.categorias import CATEGORIA_TRANSPORTE

revision: str = "0013_seed_categoria_transporte"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM categorias_egreso WHERE nombre = :n"),
        {"n": CATEGORIA_TRANSPORTE},
    ).first()
    if not exists:
        conn.execute(
            sa.text(
                "INSERT INTO categorias_egreso (nombre, descripcion, activo, orden)"
                " VALUES (:nombre, :descripcion, :activo, :orden)"
            ),
            {
                "nombre": CATEGORIA_TRANSPORTE,
                "descripcion": "Transporte (Uber/DiDi)",
                "activo": True,
                "orden": 8,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM categorias_egreso WHERE nombre = :n"),
        {"n": CATEGORIA_TRANSPORTE},
    )
