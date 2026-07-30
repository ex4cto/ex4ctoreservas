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


def test_guardar_y_buscar_es_admin(sf: sessionmaker[Session]) -> None:
    """Freelancer with es_admin=True round-trips correctly."""
    repo = SQLAFreelancerRepository(sf)
    f = Freelancer(
        id=uuid.uuid4(), nombre="Admin User", activo=True, telegram_user_id=None, es_admin=True
    )
    repo.guardar(f)
    resultado = repo.buscar_por_id(f.id)
    assert resultado is not None
    assert resultado.es_admin is True


def test_es_admin_default_false(sf: sessionmaker[Session]) -> None:
    """Freelancer created without es_admin defaults to False."""
    repo = SQLAFreelancerRepository(sf)
    f = Freelancer(id=uuid.uuid4(), nombre="Normal User", activo=True, telegram_user_id=None)
    repo.guardar(f)
    resultado = repo.buscar_por_id(f.id)
    assert resultado is not None
    assert resultado.es_admin is False


def test_buscar_por_nombre_encontrado(sf: sessionmaker[Session]) -> None:
    """buscar_por_nombre returns the freelancer when the name matches exactly."""
    repo = SQLAFreelancerRepository(sf)
    f = Freelancer(id=uuid.uuid4(), nombre="Maria Auxiliadora", activo=True, telegram_user_id=None)
    repo.guardar(f)
    resultado = repo.buscar_por_nombre("Maria Auxiliadora")
    assert resultado is not None
    assert resultado.nombre == "Maria Auxiliadora"


def test_buscar_por_nombre_no_encontrado(sf: sessionmaker[Session]) -> None:
    """buscar_por_nombre returns None when the name does not match."""
    repo = SQLAFreelancerRepository(sf)
    assert repo.buscar_por_nombre("Nadie Inexistente") is None


def test_listar_todos_activos_e_inactivos(sf: sessionmaker[Session]) -> None:
    """listar_todos returns both active and inactive freelancers ordered by name."""
    repo = SQLAFreelancerRepository(sf)
    fa = Freelancer(id=uuid.uuid4(), nombre="Activo", activo=True, telegram_user_id=None)
    fi = Freelancer(id=uuid.uuid4(), nombre="Inactivo", activo=False, telegram_user_id=None)
    repo.guardar(fa)
    repo.guardar(fi)
    todos = repo.listar_todos()
    nombres = [f.nombre for f in todos]
    assert "Activo" in nombres
    assert "Inactivo" in nombres
    assert len(todos) == 2


def test_buscar_por_telegram_id_no_devuelve_inactivos(sf: sessionmaker[Session]) -> None:
    """buscar_por_telegram_id must NOT return inactive freelancers."""
    repo = SQLAFreelancerRepository(sf)
    f = Freelancer(
        id=uuid.uuid4(), nombre="Desactivado", activo=False, telegram_user_id=77770000
    )
    repo.guardar(f)
    resultado = repo.buscar_por_telegram_id(77770000)
    assert resultado is None
