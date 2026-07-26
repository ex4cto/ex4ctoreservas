from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.persistencia.repositorios.servicios import SQLAServicioRepository


def test_guardar_y_buscar_por_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAServicioRepository(sf)
    s = Servicio(
        id=uuid.uuid4(), numero=1, nombre="City Tour", descripcion="Tour por la ciudad", activo=True
    )
    repo.guardar(s)
    resultado = repo.buscar_por_id(s.id)
    assert resultado is not None
    assert resultado.id == s.id
    assert resultado.numero == s.numero
    assert resultado.nombre == s.nombre
    assert resultado.activo is True


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAServicioRepository(sf)
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_listar_vacio(sf: sessionmaker[Session]) -> None:
    repo = SQLAServicioRepository(sf)
    assert repo.listar() == []


def test_listar_con_elementos(sf: sessionmaker[Session]) -> None:
    repo = SQLAServicioRepository(sf)
    s1 = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour A", descripcion="", activo=True)
    s2 = Servicio(id=uuid.uuid4(), numero=2, nombre="Tour B", descripcion="", activo=False)
    repo.guardar(s1)
    repo.guardar(s2)
    lista = repo.listar()
    assert len(lista) == 2


def test_listar_incluye_neto(sf: sessionmaker[Session]) -> None:
    repo = SQLAServicioRepository(sf)
    s = Servicio(
        id=uuid.uuid4(),
        numero=1,
        nombre="Tour Con Neto",
        precio_neto_adulto=Decimal("100000"),
        precio_neto_nino=Decimal("50000"),
    )
    repo.guardar(s)
    lista = repo.listar()
    assert len(lista) == 1
    assert lista[0].precio_neto_adulto == Decimal("100000")
    assert lista[0].precio_neto_nino == Decimal("50000")


def test_listar_neto_null(sf: sessionmaker[Session]) -> None:
    repo = SQLAServicioRepository(sf)
    s = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour Sin Neto")
    repo.guardar(s)
    lista = repo.listar()
    assert len(lista) == 1
    assert lista[0].precio_neto_adulto is None
    assert lista[0].precio_neto_nino is None
