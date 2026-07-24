from __future__ import annotations

import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.freelancers.entidades import Freelancer
from garay.infraestructura.persistencia.repositorios.freelancers import SQLAFreelancerRepository


def test_guardar_y_buscar_por_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAFreelancerRepository(sf)
    f = Freelancer(id=uuid.uuid4(), nombre="Ana Vendedora", activo=True, telegram_user_id=None)
    repo.guardar(f)
    resultado = repo.buscar_por_id(f.id)
    assert resultado is not None
    assert resultado.id == f.id
    assert resultado.nombre == f.nombre
    assert resultado.activo is True


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAFreelancerRepository(sf)
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_listar_activos(sf: sessionmaker[Session]) -> None:
    repo = SQLAFreelancerRepository(sf)
    f1 = Freelancer(id=uuid.uuid4(), nombre="Ana", activo=True, telegram_user_id=None)
    f2 = Freelancer(id=uuid.uuid4(), nombre="Bob", activo=False, telegram_user_id=None)
    repo.guardar(f1)
    repo.guardar(f2)
    activos = repo.listar_activos()
    assert len(activos) == 1
    assert activos[0].nombre == "Ana"


def test_buscar_por_telegram_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAFreelancerRepository(sf)
    f = Freelancer(id=uuid.uuid4(), nombre="Carlos", activo=True, telegram_user_id=99991234)
    repo.guardar(f)
    resultado = repo.buscar_por_telegram_id(99991234)
    assert resultado is not None
    assert resultado.nombre == "Carlos"
    assert repo.buscar_por_telegram_id(0) is None
