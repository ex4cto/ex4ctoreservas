from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.infraestructura.persistencia.repositorios.puntos_de_venta import (
    SQLAPuntoDeVentaRepository,
)


def test_guardar_y_buscar_por_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAPuntoDeVentaRepository(sf)
    p = PuntoDeVenta(id=uuid.uuid4(), nombre="Punto Centro", porcentaje_capa=Decimal("10.00"))
    repo.guardar(p)
    resultado = repo.buscar_por_id(p.id)
    assert resultado is not None
    assert resultado.id == p.id
    assert resultado.nombre == p.nombre
    assert resultado.porcentaje_capa == Decimal("10.00")


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAPuntoDeVentaRepository(sf)
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_listar_vacio(sf: sessionmaker[Session]) -> None:
    repo = SQLAPuntoDeVentaRepository(sf)
    assert repo.listar() == []


def test_listar_con_elementos(sf: sessionmaker[Session]) -> None:
    repo = SQLAPuntoDeVentaRepository(sf)
    p1 = PuntoDeVenta(id=uuid.uuid4(), nombre="P1", porcentaje_capa=Decimal("5.00"))
    p2 = PuntoDeVenta(id=uuid.uuid4(), nombre="P2", porcentaje_capa=Decimal("8.50"))
    repo.guardar(p1)
    repo.guardar(p2)
    assert len(repo.listar()) == 2
