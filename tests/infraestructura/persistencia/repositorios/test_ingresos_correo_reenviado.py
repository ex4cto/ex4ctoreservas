"""Tests for correo_origen/reenviado round-trip in SQLAIngresoRepository — RED phase."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Ingreso
from garay.infraestructura.persistencia.repositorios.ingresos import SQLAIngresoRepository

_UTC = datetime.UTC


def _make_ingreso(
    *,
    referencia: str = "MSG-001",
    correo_origen: str | None = None,
    reenviado: bool = False,
) -> Ingreso:
    return Ingreso(
        id=uuid.uuid4(),
        banco="Bancolombia",
        monto=Dinero("500000"),
        fecha=datetime.date(2026, 7, 30),
        referencia=referencia,
        remitente="Juan Perez",
        correo_origen=correo_origen,
        reenviado=reenviado,
    )


def test_correo_origen_round_trip(sf: sessionmaker[Session]) -> None:
    repo = SQLAIngresoRepository(sf)
    ingreso = _make_ingreso(referencia="MSG-A", correo_origen="alertas@bancolombia.com")
    repo.guardar(ingreso)

    resultado = repo.buscar_por_id(ingreso.id)

    assert resultado is not None
    assert resultado.correo_origen == "alertas@bancolombia.com"


def test_reenviado_true_round_trip(sf: sessionmaker[Session]) -> None:
    repo = SQLAIngresoRepository(sf)
    ingreso = _make_ingreso(referencia="MSG-B", reenviado=True)
    repo.guardar(ingreso)

    resultado = repo.buscar_por_id(ingreso.id)

    assert resultado is not None
    assert resultado.reenviado is True


def test_correo_origen_none_round_trip(sf: sessionmaker[Session]) -> None:
    repo = SQLAIngresoRepository(sf)
    ingreso = _make_ingreso(referencia="MSG-C", correo_origen=None)
    repo.guardar(ingreso)

    resultado = repo.buscar_por_id(ingreso.id)

    assert resultado is not None
    assert resultado.correo_origen is None


def test_reenviado_defaults_false(sf: sessionmaker[Session]) -> None:
    repo = SQLAIngresoRepository(sf)
    ingreso = _make_ingreso(referencia="MSG-D")
    repo.guardar(ingreso)

    resultado = repo.buscar_por_id(ingreso.id)

    assert resultado is not None
    assert resultado.reenviado is False
