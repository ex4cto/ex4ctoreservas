"""Smoke tests: ORM models import cleanly and schema creates without error in SQLite."""

from __future__ import annotations

import sqlalchemy as sa

from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.modelos import (  # noqa: F401
    CategoriaEgresoModel,
    ClienteModel,
    ComisionRegistradaModel,
    ConciliacionModel,
    EgresoModel,
    FreelancerModel,
    GastoRecurrenteModel,
    IngresoModel,
    PuntoDeVentaModel,
    ReglasComisionModel,
    ServicioModel,
    TiqueteraModel,
    VentaModel,
)

_EXPECTED_TABLES = {
    "servicios",
    "clientes",
    "freelancers",
    "puntos_de_venta",
    "reglas_comision",
    "ventas",
    "tiqueteras",
    "comisiones_registradas",
    "ingresos",
    "egresos",
    "conciliaciones",
    "categorias_egreso",
    "gastos_recurrentes",
}


def test_schema_creates_all_tables_in_sqlite() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(sa.inspect(engine).get_table_names())
    assert tables == _EXPECTED_TABLES


def test_venta_columns_present() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = sa.inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("ventas")}
    assert {
        "id",
        "valor_venta",
        "neto",
        "abono",
        "servicio_ids",
        "cliente_id",
        "tipo_cliente",
        "fecha",
        "adultos",
        "ninos",
        "estado",
        "vendedor_nombre",
        "cerrador_nombre",
        "punto_de_venta_id",
        "referido_nombre",
    }.issubset(cols)


def test_tiquetera_has_both_ticket_fields() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = sa.inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("tiqueteras")}
    assert "numero_fisico" in cols
    assert "numero_ticket" in cols


def test_comision_registrada_has_snapshot_json() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = sa.inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("comisiones_registradas")}
    assert "snapshot_json" in cols
    assert {"vendedor", "cerrador", "punto_de_venta", "referido", "agencia"}.issubset(cols)
