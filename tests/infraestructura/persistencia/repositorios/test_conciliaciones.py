"""Tests for SQLAConciliacionRepository."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Conciliacion, Ingreso
from garay.dominio.conciliacion.tipos import EstadoConciliacion
from garay.infraestructura.persistencia.repositorios.conciliaciones import (
    SQLAConciliacionRepository,
)
from garay.infraestructura.persistencia.repositorios.ingresos import SQLAIngresoRepository


def _make_ingreso(referencia: str = "REF-001") -> Ingreso:
    return Ingreso(
        id=uuid.uuid4(),
        banco="Bancolombia",
        monto=Dinero("100000"),
        fecha=datetime.date(2026, 7, 1),
        referencia=referencia,
    )


def _make_conciliacion(
    ingreso_id: uuid.UUID,
    *,
    estado: EstadoConciliacion = EstadoConciliacion.PENDIENTE,
    venta_id: uuid.UUID | None = None,
    score: Decimal | None = None,
    confianza: Decimal | None = None,
) -> Conciliacion:
    return Conciliacion(
        id=uuid.uuid4(),
        ingreso_id=ingreso_id,
        venta_id=venta_id,
        estado=estado,
        score=score,
        confianza=confianza,
    )


def test_guardar_y_buscar_por_ingreso_id(sf: sessionmaker[Session]) -> None:
    ingreso_repo = SQLAIngresoRepository(sf)
    ingreso = _make_ingreso()
    ingreso_repo.guardar(ingreso)

    repo = SQLAConciliacionRepository(sf)
    conc = _make_conciliacion(ingreso.id)
    repo.guardar(conc)

    resultado = repo.buscar_por_ingreso_id(ingreso.id)
    assert resultado is not None
    assert resultado.ingreso_id == ingreso.id


def test_guardar_y_buscar_por_id(sf: sessionmaker[Session]) -> None:
    ingreso_repo = SQLAIngresoRepository(sf)
    ingreso = _make_ingreso("REF-002")
    ingreso_repo.guardar(ingreso)

    repo = SQLAConciliacionRepository(sf)
    conc = _make_conciliacion(ingreso.id)
    repo.guardar(conc)

    resultado = repo.buscar_por_id(conc.id)
    assert resultado is not None
    assert resultado.id == conc.id


def test_guardar_preserva_score_y_confianza(sf: sessionmaker[Session]) -> None:
    ingreso_repo = SQLAIngresoRepository(sf)
    ingreso = _make_ingreso("REF-003")
    ingreso_repo.guardar(ingreso)

    repo = SQLAConciliacionRepository(sf)
    conc = _make_conciliacion(
        ingreso.id,
        score=Decimal("0.9500"),
        confianza=Decimal("0.9500"),
    )
    repo.guardar(conc)

    resultado = repo.buscar_por_id(conc.id)
    assert resultado is not None
    assert resultado.score == Decimal("0.9500")
    assert resultado.confianza == Decimal("0.9500")


def test_listar_pendientes_filtra_estados(sf: sessionmaker[Session]) -> None:
    ingreso_repo = SQLAIngresoRepository(sf)
    i1 = _make_ingreso("REF-P1")
    i2 = _make_ingreso("REF-P2")
    i3 = _make_ingreso("REF-P3")
    ingreso_repo.guardar(i1)
    ingreso_repo.guardar(i2)
    ingreso_repo.guardar(i3)

    repo = SQLAConciliacionRepository(sf)
    repo.guardar(_make_conciliacion(i1.id, estado=EstadoConciliacion.PENDIENTE))
    repo.guardar(_make_conciliacion(i2.id, estado=EstadoConciliacion.SIN_MATCH))
    repo.guardar(_make_conciliacion(i3.id, estado=EstadoConciliacion.MATCHEADO))

    pendientes = repo.listar_pendientes()
    ids_estado = {c.estado for c in pendientes}
    assert EstadoConciliacion.MATCHEADO not in ids_estado
    assert len(pendientes) == 2  # PENDIENTE + SIN_MATCH


def test_listar_ingreso_ids_procesados(sf: sessionmaker[Session]) -> None:
    ingreso_repo = SQLAIngresoRepository(sf)
    i1 = _make_ingreso("REF-IP1")
    i2 = _make_ingreso("REF-IP2")
    ingreso_repo.guardar(i1)
    ingreso_repo.guardar(i2)

    repo = SQLAConciliacionRepository(sf)
    repo.guardar(_make_conciliacion(i1.id))
    repo.guardar(_make_conciliacion(i2.id))

    ids_procesados = repo.listar_ingreso_ids_procesados()
    assert i1.id in ids_procesados
    assert i2.id in ids_procesados


def test_buscar_por_id_no_existe_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAConciliacionRepository(sf)
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_buscar_por_ingreso_id_no_existe_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAConciliacionRepository(sf)
    assert repo.buscar_por_ingreso_id(uuid.uuid4()) is None
