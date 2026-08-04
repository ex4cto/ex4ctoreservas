"""Add punto_de_venta_nombre and numero_personas to reglas_comision.

Replaces the anonymous unique constraint on tipo_cliente with a composite
unique on (tipo_cliente, punto_de_venta_nombre, numero_personas) to support
point-specific commission rules (e.g., Crespo with 1 or 2 persons).

Pre-check (S6): aborts if any existing DIGITAL venta has a punto_de_venta_id,
as the DigitalConPuntoDeVenta domain invariant would be violated for such rows.

copy_from usage: both upgrade() and downgrade() supply an explicit sa.Table
source to batch_alter_table so that Alembic reflects from a known schema
instead of the live table. This is required because SQLite reflection carries
any unnamed unique constraint forward into the copy-recreated table. Without
copy_from the old anonymous unique(tipo_cliente) from 0000_initial_schema
would survive the recreate and co-exist with the new composite unique,
causing IntegrityError when Crespo rows (all EXTERNO) are inserted.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

# Explicit source schema for upgrade's copy_from.
# Mirrors the 0000_initial_schema definition of reglas_comision WITHOUT the
# anonymous UniqueConstraint("tipo_cliente") so that the recreated table starts
# clean and the batch_op can add only the composite unique constraint.
_SOURCE_PRE_0008 = sa.Table(
    "reglas_comision",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("tipo_cliente", sa.String(), nullable=False),
    sa.Column("porcentaje_vendedor", sa.Numeric(5, 2), nullable=False),
    sa.Column("porcentaje_cerrador", sa.Numeric(5, 2), nullable=False),
    sa.Column("porcentaje_referido_maximo", sa.Numeric(5, 2), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    # NOTE: UniqueConstraint("tipo_cliente") intentionally omitted.
)

# Explicit source schema for downgrade's copy_from.
# Mirrors the 0008 table (all 7 columns + the composite unique) so the
# recreate starts from a known state and we can surgically drop the composite
# unique and the two new columns, then restore the anonymous unique.
_SOURCE_POST_0008 = sa.Table(
    "reglas_comision",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("tipo_cliente", sa.String(), nullable=False),
    sa.Column("porcentaje_vendedor", sa.Numeric(5, 2), nullable=False),
    sa.Column("porcentaje_cerrador", sa.Numeric(5, 2), nullable=False),
    sa.Column("porcentaje_referido_maximo", sa.Numeric(5, 2), nullable=False),
    sa.Column("punto_de_venta_nombre", sa.String(), nullable=True),
    sa.Column("numero_personas", sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint(
        "tipo_cliente",
        "punto_de_venta_nombre",
        "numero_personas",
        name="uq_reglas_tipo_punto_personas",
    ),
)


def upgrade() -> None:
    # S6: pre-check — fail loudly if any DIGITAL venta has a punto_de_venta_id.
    # This ensures the DigitalConPuntoDeVenta domain invariant is safe to enable.
    conn = op.get_bind()
    n: int = conn.execute(
        sa.text(
            "SELECT count(*) FROM ventas "
            "WHERE tipo_cliente = 'DIGITAL' AND punto_de_venta_id IS NOT NULL"
        )
    ).scalar() or 0
    if n:
        raise RuntimeError(
            f"{n} venta(s) DIGITAL with punto_de_venta_id found. "
            "Clean up these rows before running migration 0008."
        )

    # copy_from=_SOURCE_PRE_0008 tells Alembic to recreate from our explicit
    # schema (without the anonymous unique) instead of reflecting the live table.
    # This prevents the old unique(tipo_cliente) from surviving the recreate.
    with op.batch_alter_table(
        "reglas_comision", recreate="always", copy_from=_SOURCE_PRE_0008
    ) as batch_op:
        batch_op.add_column(sa.Column("punto_de_venta_nombre", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("numero_personas", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_reglas_tipo_punto_personas",
            ["tipo_cliente", "punto_de_venta_nombre", "numero_personas"],
        )


def downgrade() -> None:
    # Remove Crespo-specific rows first so the restored unique(tipo_cliente)
    # is satisfiable even if the seed was already applied.
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM reglas_comision WHERE punto_de_venta_nombre IS NOT NULL")
    )

    # copy_from=_SOURCE_POST_0008 provides the current (0008) schema so the
    # recreate knows the full column set and the composite unique to remove.
    # The restored unique on tipo_cliente is given a stable name because
    # batch_alter_table with copy_from requires named constraints; the original
    # 0000 schema used an inline UNIQUE (anonymous), but a named equivalent
    # is semantically identical and avoids the "Constraint must have a name" error.
    with op.batch_alter_table(
        "reglas_comision", recreate="always", copy_from=_SOURCE_POST_0008
    ) as batch_op:
        batch_op.drop_constraint("uq_reglas_tipo_punto_personas", type_="unique")
        batch_op.drop_column("punto_de_venta_nombre")
        batch_op.drop_column("numero_personas")
        batch_op.create_unique_constraint("uq_reglas_tipo_cliente", ["tipo_cliente"])
