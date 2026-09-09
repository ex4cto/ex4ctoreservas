"""Seed the remaining egreso categories.

Revision ID: 0018_seed_categorias_egreso
Revises: 0017
Create Date: 2026-09-09 00:00:00.000000

Inserts the categories the manual-egreso flow needs, besides 'transporte'
(already seeded by 0013). Includes 'otro', the fallback used by the automatic
bank classification (banco_a_categoria).

Idempotent: each row is inserted only if its nombre is not already present, so
re-running ``alembic upgrade head`` on an already-migrated database is safe and
a pre-existing 'transporte' row is left untouched.
downgrade() deletes exactly the rows this migration seeds.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_seed_categorias_egreso"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (nombre, descripcion, orden). 'transporte' (orden 8) is owned by 0013.
_CATEGORIAS: list[tuple[str, str, int]] = [
    ("comisiones", "Comisiones pagadas a freelancers", 1),
    ("proveedores tour", "Proveedores de tour (lanchas, entradas, guias)", 2),
    ("alimentación", "Alimentacion (comidas, refrigerios)", 3),
    ("marketing", "Marketing y publicidad", 4),
    ("servicios fijos", "Servicios fijos (arriendo, internet, publicos)", 5),
    ("software", "Software y herramientas", 6),
    ("bancarios/impuestos", "Gastos bancarios e impuestos", 7),
    ("otro", "Otros gastos", 9),
]


def upgrade() -> None:
    conn = op.get_bind()
    for nombre, descripcion, orden in _CATEGORIAS:
        exists = conn.execute(
            sa.text("SELECT 1 FROM categorias_egreso WHERE nombre = :n"),
            {"n": nombre},
        ).first()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO categorias_egreso (nombre, descripcion, activo, orden)"
                    " VALUES (:nombre, :descripcion, :activo, :orden)"
                ),
                {
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "activo": True,
                    "orden": orden,
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    for nombre, _descripcion, _orden in _CATEGORIAS:
        conn.execute(
            sa.text("DELETE FROM categorias_egreso WHERE nombre = :n"),
            {"n": nombre},
        )
