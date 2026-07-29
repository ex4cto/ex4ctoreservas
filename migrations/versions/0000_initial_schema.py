"""Initial schema — all base tables before incremental migrations.

Revision ID: 0000
Revises:
Create Date: 2026-07-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import garay.infraestructura.persistencia.tipos  # noqa: F401

revision: str = "0000"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute(sa.schema.CreateSequence(sa.Sequence("ticket_seq")))

    op.create_table(
        "servicios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero"),
    )

    op.create_table(
        "clientes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("telefono", sa.String(), nullable=True),
        sa.Column("hotel", sa.String(), nullable=True),
        sa.Column("numero_habitacion", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "freelancers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
    )

    op.create_table(
        "puntos_de_venta",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("porcentaje_capa", sa.Numeric(5, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "reglas_comision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tipo_cliente", sa.String(), nullable=False),
        sa.Column("porcentaje_vendedor", sa.Numeric(5, 2), nullable=False),
        sa.Column("porcentaje_cerrador", sa.Numeric(5, 2), nullable=False),
        sa.Column("porcentaje_referido_maximo", sa.Numeric(5, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tipo_cliente"),
    )

    op.create_table(
        "ventas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("valor_venta", garay.infraestructura.persistencia.tipos.TipoDinero(), nullable=False),
        sa.Column("neto", garay.infraestructura.persistencia.tipos.TipoDinero(), nullable=False),
        sa.Column("abono", garay.infraestructura.persistencia.tipos.TipoDinero(), nullable=True),
        sa.Column("servicio_ids", sa.JSON(), nullable=False),
        sa.Column("cliente_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_cliente", sa.String(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("adultos", sa.Integer(), nullable=False),
        sa.Column("ninos", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False),
        sa.Column("vendedor_nombre", sa.String(), nullable=True),
        sa.Column("cerrador_nombre", sa.String(), nullable=True),
        sa.Column("punto_de_venta_id", sa.Uuid(), nullable=True),
        sa.Column("referido_nombre", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"]),
        sa.ForeignKeyConstraint(["punto_de_venta_id"], ["puntos_de_venta.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tiqueteras",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("venta_id", sa.Uuid(), nullable=False),
        sa.Column("foto_referencia", sa.String(), nullable=False),
        sa.Column("numero_fisico", sa.BigInteger(), nullable=True),
        sa.Column("numero_ticket", sa.BigInteger(), sa.Sequence("ticket_seq"), nullable=True),
        sa.Column("procesada", sa.Boolean(), nullable=False),
        sa.Column("datos_extraidos", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["venta_id"], ["ventas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero_ticket"),
        sa.UniqueConstraint("venta_id"),
    )

    op.create_table(
        "comisiones_registradas",
        sa.Column("venta_id", sa.Uuid(), nullable=False),
        sa.Column("vendedor", garay.infraestructura.persistencia.tipos.TipoDinero(), nullable=False),
        sa.Column("cerrador", garay.infraestructura.persistencia.tipos.TipoDinero(), nullable=False),
        sa.Column("punto_de_venta", garay.infraestructura.persistencia.tipos.TipoDinero(), nullable=False),
        sa.Column("referido", garay.infraestructura.persistencia.tipos.TipoDinero(), nullable=False),
        sa.Column("agencia", garay.infraestructura.persistencia.tipos.TipoDinero(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["venta_id"], ["ventas.id"]),
        sa.PrimaryKeyConstraint("venta_id"),
    )

    op.create_table(
        "ingresos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("banco", sa.String(), nullable=False),
        sa.Column("monto", garay.infraestructura.persistencia.tipos.TipoDinero(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("referencia", sa.String(), nullable=False),
        sa.Column("remitente", sa.String(), nullable=True),
        sa.Column("clasificado", sa.Boolean(), nullable=False),
        sa.Column("venta_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["venta_id"], ["ventas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "egresos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=False),
        sa.Column("monto", garay.infraestructura.persistencia.tipos.TipoDinero(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("categoria", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "conciliaciones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingreso_id", sa.Uuid(), nullable=False),
        sa.Column("venta_id", sa.Uuid(), nullable=True),
        sa.Column("estado", sa.String(), nullable=False),
        sa.Column("notas", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["ingreso_id"], ["ingresos.id"]),
        sa.ForeignKeyConstraint(["venta_id"], ["ventas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("conciliaciones")
    op.drop_table("egresos")
    op.drop_table("ingresos")
    op.drop_table("comisiones_registradas")
    op.drop_table("tiqueteras")
    op.drop_table("ventas")
    op.drop_table("reglas_comision")
    op.drop_table("puntos_de_venta")
    op.drop_table("freelancers")
    op.drop_table("clientes")
    op.drop_table("servicios")
    op.execute(sa.schema.DropSequence(sa.Sequence("ticket_seq")))
