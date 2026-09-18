"""Add obligaciones_hotel table, migrate hotel data from gastos_recurrentes.

Revision ID: 0026
Revises: e5f6a7b8c9d0
Create Date: 2026-09-18 00:00:00.000000

Schema changes:
  - CREATE TABLE obligaciones_hotel
  - ALTER TABLE egresos ADD COLUMN obligacion_hotel_id UUID FK obligaciones_hotel(id)

Data migration (upgrade):
  - DELETE gastos_recurrentes WHERE nombre LIKE 'Arriendo punto%' (3 hotel entries)
  - INSERT 4 rows into obligaciones_hotel (Hotel Marie, Mama Waldy, Hostal Dora, Crespo)
  - INSERT 1 row into gastos_recurrentes (Plan telefono 1, $60,000/mes)

Data migration (downgrade):
  - DELETE the 4 obligaciones_hotel rows
  - Re-INSERT the 3 Arriendo punto rows into gastos_recurrentes
  - DELETE the Plan telefono 1 row from gastos_recurrentes
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Stable UUIDs for the 4 hotel obligations — deterministic so downgrade can target them.
_UUID_HOTEL_MARIE = "11111111-0001-0001-0001-000000000001"
_UUID_MAMA_WALDY = "11111111-0002-0002-0002-000000000002"
_UUID_HOSTAL_DORA = "11111111-0003-0003-0003-000000000003"
_UUID_CRESPO = "11111111-0004-0004-0004-000000000004"

# Stable UUID for the new Plan telefono gasto_recurrente row.
_UUID_PLAN_TELEFONO = "11111111-0010-0010-0010-000000000010"

# Stable UUIDs for the 3 Arriendo punto rows being restored in downgrade.
_UUID_ARRIENDO_MARIE = "22222222-0001-0001-0001-000000000001"
_UUID_ARRIENDO_WALDY = "22222222-0002-0002-0002-000000000002"
_UUID_ARRIENDO_DORA = "22222222-0003-0003-0003-000000000003"


def upgrade() -> None:
    # --- Schema: create obligaciones_hotel table ---
    op.create_table(
        "obligaciones_hotel",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("punto_de_venta_nombre", sa.String(), nullable=False),
        sa.Column("receptor_nombre", sa.String(), nullable=False),
        sa.Column("monto_cuota_dia_1", sa.Numeric(14, 2), nullable=False),
        sa.Column("monto_cuota_dia_2", sa.Numeric(14, 2), nullable=True),
        sa.Column("dia_pago_1", sa.Integer(), nullable=False),
        sa.Column("dia_pago_2", sa.Integer(), nullable=True),
        sa.Column(
            "deuda_inicial",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("fecha_deuda_inicial", sa.Date(), nullable=False),
        sa.Column(
            "activa",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # --- Schema: add obligacion_hotel_id FK to egresos ---
    op.add_column(
        "egresos",
        sa.Column(
            "obligacion_hotel_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("obligaciones_hotel.id"),
            nullable=True,
        ),
    )

    conn = op.get_bind()

    # --- Data: remove hotel entries from gastos_recurrentes ---
    conn.execute(
        sa.text("DELETE FROM gastos_recurrentes WHERE nombre LIKE 'Arriendo punto%'")
    )

    # --- Data: insert 4 hotel obligations ---
    conn.execute(
        sa.text(
            "INSERT INTO obligaciones_hotel "
            "(id, punto_de_venta_nombre, receptor_nombre, "
            " monto_cuota_dia_1, monto_cuota_dia_2, "
            " dia_pago_1, dia_pago_2, deuda_inicial, fecha_deuda_inicial, activa)"
            " VALUES "
            # Hotel Marie — deuda_inicial=0 (monto real pendiente de confirmacion)
            "(:id1, 'Hotel Marie', 'Abel', 1000000, 1000000, 15, 30,"
            "  0, '2026-01-01', TRUE),"  # TODO: actualizar cuando Sharimel confirme el monto
            "(:id2, 'Mama Waldy', 'German', 750000, 950000, 15, 30,"
            "  2350000, '2026-01-01', TRUE),"
            "(:id3, 'Hostal Dora', 'Waldy', 400000, 400000, 15, 30,"
            "  2400000, '2026-01-01', TRUE),"
            # Crespo — no dia_pago_2 / cuota_dia_2
            "(:id4, 'Crespo', 'Pendiente', 500000, NULL, 15, NULL,"
            "  500000, '2026-01-01', TRUE)"
        ),
        {
            "id1": _UUID_HOTEL_MARIE,
            "id2": _UUID_MAMA_WALDY,
            "id3": _UUID_HOSTAL_DORA,
            "id4": _UUID_CRESPO,
        },
    )

    # --- Data: insert Plan telefono 1 as a new gasto_recurrente ---
    conn.execute(
        sa.text(
            "INSERT INTO gastos_recurrentes (id, nombre, monto, categoria, dia_mes, activo)"
            " VALUES (:id, 'Plan telefono 1', 60000, 'otro', 1, TRUE)"
        ),
        {"id": _UUID_PLAN_TELEFONO},
    )


def downgrade() -> None:
    conn = op.get_bind()

    # --- Data: remove Plan telefono 1 ---
    conn.execute(
        sa.text("DELETE FROM gastos_recurrentes WHERE id = :id"),
        {"id": _UUID_PLAN_TELEFONO},
    )

    # --- Data: remove the 4 hotel obligations ---
    conn.execute(
        sa.text(
            "DELETE FROM obligaciones_hotel WHERE id IN (:id1, :id2, :id3, :id4)"
        ),
        {
            "id1": _UUID_HOTEL_MARIE,
            "id2": _UUID_MAMA_WALDY,
            "id3": _UUID_HOSTAL_DORA,
            "id4": _UUID_CRESPO,
        },
    )

    # --- Data: re-insert the 3 Arriendo punto rows ---
    conn.execute(
        sa.text(
            "INSERT INTO gastos_recurrentes (id, nombre, monto, categoria, dia_mes, activo)"
            " VALUES "
            "(:id1, 'Arriendo punto Hotel Marie', 1000000, 'servicios fijos', 15, TRUE),"
            "(:id2, 'Arriendo punto Mama Waldy', 750000, 'servicios fijos', 15, TRUE),"
            "(:id3, 'Arriendo punto Hostal Dora', 400000, 'servicios fijos', 15, TRUE)"
        ),
        {
            "id1": _UUID_ARRIENDO_MARIE,
            "id2": _UUID_ARRIENDO_WALDY,
            "id3": _UUID_ARRIENDO_DORA,
        },
    )

    # --- Schema: drop obligacion_hotel_id from egresos ---
    op.drop_column("egresos", "obligacion_hotel_id")

    # --- Schema: drop obligaciones_hotel table ---
    op.drop_table("obligaciones_hotel")
