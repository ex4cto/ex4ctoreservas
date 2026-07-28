"""Tests for SQLAIngresoRepository — TDD RED phase."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Ingreso
from garay.infraestructura.persistencia.repositorios.ingresos import SQLAIngresoRepository


def _make_ingreso(*, referencia: str = "MSG-001", clasificado: bool = False) -> Ingreso:
    return Ingreso(
        id=uuid.uuid4(),
        banco="Bancolombia",
        monto=Dinero("500000"),
        fecha=datetime.date(2026, 7, 15),
        referencia=referencia,
        remitente="Juan Perez",
        clasificado=clasificado,
    )


def test_guardar_y_buscar_por_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAIngresoRepository(sf)
    ingreso = _make_ingreso()

    repo.guardar(ingreso)
    resultado = repo.buscar_por_id(ingreso.id)

    assert resultado is not None
    assert resultado.id == ingreso.id
    assert resultado.banco == "Bancolombia"
    assert resultado.monto == Dinero("500000")
    assert resultado.referencia == "MSG-001"
    assert resultado.remitente == "Juan Perez"
    assert resultado.clasificado is False


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAIngresoRepository(sf)
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_listar_sin_clasificar(sf: sessionmaker[Session]) -> None:
    repo = SQLAIngresoRepository(sf)
    i1 = _make_ingreso(referencia="MSG-A", clasificado=False)
    i2 = _make_ingreso(referencia="MSG-B", clasificado=True)
    i3 = _make_ingreso(referencia="MSG-C", clasificado=False)

    repo.guardar(i1)
    repo.guardar(i2)
    repo.guardar(i3)

    resultado = repo.listar_sin_clasificar()

    ids = {r.id for r in resultado}
    assert i1.id in ids
    assert i3.id in ids
    assert i2.id not in ids


def test_existe_referencia_verdadero(sf: sessionmaker[Session]) -> None:
    repo = SQLAIngresoRepository(sf)
    ingreso = _make_ingreso(referencia="MSG-UNICO")
    repo.guardar(ingreso)

    assert repo.existe_referencia("MSG-UNICO") is True


def test_existe_referencia_falso(sf: sessionmaker[Session]) -> None:
    repo = SQLAIngresoRepository(sf)

    assert repo.existe_referencia("MSG-INEXISTENTE") is False
