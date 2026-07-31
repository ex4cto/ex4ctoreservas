from __future__ import annotations

import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comun.tipos import TipoCliente
from garay.infraestructura.persistencia.repositorios.clientes import SQLAClienteRepository


def test_guardar_y_buscar_por_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAClienteRepository(sf)
    c = Cliente(
        id=uuid.uuid4(),
        nombre="Juan Perez",
        tipo=TipoCliente.EXTERNO,
        telefono="3001234567",
        hotel=None,
        numero_habitacion=None,
    )
    repo.guardar(c)
    resultado = repo.buscar_por_id(c.id)
    assert resultado is not None
    assert resultado.id == c.id
    assert resultado.nombre == c.nombre
    assert resultado.tipo == TipoCliente.EXTERNO


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAClienteRepository(sf)
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_buscar_por_nombre(sf: sessionmaker[Session]) -> None:
    repo = SQLAClienteRepository(sf)
    c = Cliente(
        id=uuid.uuid4(),
        nombre="Maria Lopez",
        tipo=TipoCliente.EXTERNO,
        telefono="3009998888",
        hotel=None,
        numero_habitacion=None,
    )
    repo.guardar(c)
    resultado = repo.buscar_por_nombre("Maria Lopez")
    assert resultado is not None
    assert resultado.id == c.id
    assert resultado.nombre == "Maria Lopez"


def test_buscar_por_nombre_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAClienteRepository(sf)
    assert repo.buscar_por_nombre("No Existe") is None
