"""Smoke tests: ORM models import cleanly and schema creates without error in SQLite."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.modelos import (  # noqa: F401
    CategoriaEgresoModel,
    ClienteModel,
    ComisionRegistradaModel,
    ConciliacionModel,
    CorreoNoParseadoModel,
    EgresoModel,
    FacturaModel,
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
    "facturas",
    "correos_no_parseados",
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


def test_freelancer_tiene_columnas_identidad() -> None:
    """FreelancerModel must expose nombre_completo, cedula, and display columns."""
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = sa.inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("freelancers")}
    assert {"nombre_completo", "cedula", "display"}.issubset(cols)


def test_freelancer_cedula_unique_constraint_rechaza_duplicados() -> None:
    """Inserting two rows with the same non-NULL cedula raises IntegrityError."""
    import uuid as _uuid

    from sqlalchemy.exc import IntegrityError

    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(
            FreelancerModel.__table__.insert(),
            [
                {
                    "id": _uuid.uuid4(),
                    "nombre": "Ana",
                    "activo": True,
                    "telegram_user_id": None,
                    "es_admin": False,
                    "nombre_completo": None,
                    "cedula": "12345678",
                    "display": None,
                },
            ],
        )
        conn.commit()

        with pytest.raises(IntegrityError):
            conn.execute(
                FreelancerModel.__table__.insert(),
                [
                    {
                        "id": _uuid.uuid4(),
                        "nombre": "Bob",
                        "activo": True,
                        "telegram_user_id": None,
                        "es_admin": False,
                        "nombre_completo": None,
                        "cedula": "12345678",
                        "display": None,
                    },
                ],
            )
            conn.commit()


def test_freelancer_cedula_null_permitido_en_multiples_filas() -> None:
    """Multiple rows with cedula=NULL must coexist (NULL is not a conflict)."""
    import uuid as _uuid

    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(
            FreelancerModel.__table__.insert(),
            [
                {
                    "id": _uuid.uuid4(),
                    "nombre": "Legacy1",
                    "activo": True,
                    "telegram_user_id": None,
                    "es_admin": False,
                    "nombre_completo": None,
                    "cedula": None,
                    "display": None,
                },
                {
                    "id": _uuid.uuid4(),
                    "nombre": "Legacy2",
                    "activo": True,
                    "telegram_user_id": None,
                    "es_admin": False,
                    "nombre_completo": None,
                    "cedula": None,
                    "display": None,
                },
            ],
        )
        conn.commit()

    with engine.connect() as conn:
        result = conn.execute(FreelancerModel.__table__.select()).fetchall()
        assert len(result) == 2


def test_venta_tiene_vendedor_id_y_cerrador_id_nullable() -> None:
    """Slice B: ventas table must have nullable vendedor_id and cerrador_id FK columns."""
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = sa.inspect(engine)
    cols_by_name = {c["name"]: c for c in inspector.get_columns("ventas")}

    assert "vendedor_id" in cols_by_name, "vendedor_id column missing from ventas"
    assert "cerrador_id" in cols_by_name, "cerrador_id column missing from ventas"
    assert cols_by_name["vendedor_id"]["nullable"] is True, "vendedor_id must be nullable"
    assert cols_by_name["cerrador_id"]["nullable"] is True, "cerrador_id must be nullable"


def test_venta_vendedor_cerrador_ids_son_fk_a_freelancers() -> None:
    """Slice B: vendedor_id and cerrador_id are FK-constrained to freelancers.id."""
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = sa.inspect(engine)
    fks = inspector.get_foreign_keys("ventas")
    fk_targets = {
        (tuple(fk["constrained_columns"]), fk["referred_table"])
        for fk in fks
    }
    assert (("vendedor_id",), "freelancers") in fk_targets, (
        "vendedor_id FK to freelancers.id missing"
    )
    assert (("cerrador_id",), "freelancers") in fk_targets, (
        "cerrador_id FK to freelancers.id missing"
    )


def test_correos_no_parseados_table_has_expected_columns() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = sa.inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("correos_no_parseados")}
    assert {
        "id",
        "banco",
        "direccion",
        "referencia",
        "asunto",
        "correo_origen",
        "cuerpo_texto",
        "cuerpo_html",
        "error_parseo",
        "fecha_recibido",
        "procesado",
        "intentos",
        "error_ultimo",
    }.issubset(cols)
