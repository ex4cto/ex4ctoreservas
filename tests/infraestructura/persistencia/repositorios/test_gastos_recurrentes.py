"""Tests for SQLAGastoRecurrenteRepository — RED phase."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import GastoRecurrente
from garay.infraestructura.persistencia.repositorios.gastos_recurrentes import (
    SQLAGastoRecurrenteRepository,
)


def _gasto(nombre: str = "Arriendo", activo: bool = True) -> GastoRecurrente:
    return GastoRecurrente(
        id=uuid.uuid4(),
        nombre=nombre,
        monto=Dinero("500000"),
        categoria="arriendo",
        dia_mes=1,
        activo=activo,
    )


def test_guardar_y_buscar_por_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAGastoRecurrenteRepository(sf)
    gasto = _gasto()
    repo.guardar(gasto)

    resultado = repo.buscar_por_id(gasto.id)
    assert resultado is not None
    assert resultado.id == gasto.id
    assert resultado.nombre == "Arriendo"
    assert resultado.monto == Dinero("500000")
    assert resultado.categoria == "arriendo"
    assert resultado.dia_mes == 1
    assert resultado.activo is True


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAGastoRecurrenteRepository(sf)
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_listar_activos(sf: sessionmaker[Session]) -> None:
    repo = SQLAGastoRecurrenteRepository(sf)
    repo.guardar(_gasto("Arriendo", activo=True))
    repo.guardar(_gasto("Nomina", activo=True))
    repo.guardar(_gasto("Inactivo", activo=False))

    activos = repo.listar_activos()
    nombres = [g.nombre for g in activos]
    assert "Arriendo" in nombres
    assert "Nomina" in nombres
    assert "Inactivo" not in nombres


def test_listar_activos_ordenado_por_nombre(sf: sessionmaker[Session]) -> None:
    repo = SQLAGastoRecurrenteRepository(sf)
    repo.guardar(_gasto("Zorro"))
    repo.guardar(_gasto("Alfa"))
    repo.guardar(_gasto("Medio"))

    activos = repo.listar_activos()
    nombres = [g.nombre for g in activos]
    assert nombres == sorted(nombres)


def test_desactivar(sf: sessionmaker[Session]) -> None:
    repo = SQLAGastoRecurrenteRepository(sf)
    gasto = _gasto()
    repo.guardar(gasto)

    repo.desactivar(gasto.id)

    resultado = repo.buscar_por_id(gasto.id)
    assert resultado is not None
    assert resultado.activo is False


def test_listar_activos_vacio(sf: sessionmaker[Session]) -> None:
    repo = SQLAGastoRecurrenteRepository(sf)
    assert repo.listar_activos() == []
