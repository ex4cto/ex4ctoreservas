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


def test_buscar_por_nombre(sf: sessionmaker[Session]) -> None:
    repo = SQLAServicioRepository(sf)
    s = Servicio(id=uuid.uuid4(), numero=1, nombre="City Tour", descripcion="", activo=True)
    repo.guardar(s)
    resultado = repo.buscar_por_nombre("City Tour")
    assert resultado is not None
    assert resultado.id == s.id
    assert resultado.nombre == "City Tour"


def test_buscar_por_nombre_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAServicioRepository(sf)
    assert repo.buscar_por_nombre("No Existe") is None


def test_categoria_persiste(sf: sessionmaker[Session]) -> None:
    repo = SQLAServicioRepository(sf)
    s = Servicio(
        id=uuid.uuid4(),
        numero=1,
        nombre="Tour Con Categoria",
        categoria="TOURS BAHIA",
    )
    repo.guardar(s)
    resultado = repo.buscar_por_id(s.id)
    assert resultado is not None
    assert resultado.categoria == "TOURS BAHIA"


def test_categoria_default_vacia(sf: sessionmaker[Session]) -> None:
    repo = SQLAServicioRepository(sf)
    s = Servicio(id=uuid.uuid4(), numero=2, nombre="Sin Categoria")
    repo.guardar(s)
    resultado = repo.buscar_por_id(s.id)
    assert resultado is not None
    assert resultado.categoria == ""


# ── siguiente_numero ──────────────────────────────────────────────────────────


def test_siguiente_numero_tabla_vacia(sf: sessionmaker[Session]) -> None:
    """siguiente_numero() returns 1 when no tours exist (satisfies numero >= 1)."""
    repo = SQLAServicioRepository(sf)
    assert repo.siguiente_numero() == 1


def test_siguiente_numero_con_tours_existentes(sf: sessionmaker[Session]) -> None:
    """siguiente_numero() returns max(numero) + 1 when tours exist."""
    repo = SQLAServicioRepository(sf)
    for num, nombre in [(1, "Tour A"), (3, "Tour B"), (5, "Tour C")]:
        repo.guardar(Servicio(id=uuid.uuid4(), numero=num, nombre=nombre))
    assert repo.siguiente_numero() == 6


def test_siguiente_numero_incluye_inactivos(sf: sessionmaker[Session]) -> None:
    """siguiente_numero() uses MAX over ALL rows, including inactive tours."""
    repo = SQLAServicioRepository(sf)
    repo.guardar(Servicio(id=uuid.uuid4(), numero=10, nombre="Inactivo", activo=False))
    repo.guardar(Servicio(id=uuid.uuid4(), numero=3, nombre="Activo", activo=True))
    # MAX is 10 (inactive), so next is 11 — inactive tours are not excluded
    assert repo.siguiente_numero() == 11


# ── listar_activos ────────────────────────────────────────────────────────────


def test_listar_activos_solo_activos(sf: sessionmaker[Session]) -> None:
    """listar_activos() returns only tours where activo=True."""
    repo = SQLAServicioRepository(sf)
    activo = Servicio(id=uuid.uuid4(), numero=10, nombre="Tour Activo", activo=True)
    inactivo = Servicio(id=uuid.uuid4(), numero=11, nombre="Tour Inactivo", activo=False)
    repo.guardar(activo)
    repo.guardar(inactivo)
    resultado = repo.listar_activos()
    ids = {s.id for s in resultado}
    assert activo.id in ids
    assert inactivo.id not in ids


def test_listar_activos_vacio(sf: sessionmaker[Session]) -> None:
    """listar_activos() returns empty list when no active tours exist."""
    repo = SQLAServicioRepository(sf)
    inactivo = Servicio(id=uuid.uuid4(), numero=20, nombre="Solo Inactivo", activo=False)
    repo.guardar(inactivo)
    assert repo.listar_activos() == []


def test_listar_sigue_devolviendo_todos(sf: sessionmaker[Session]) -> None:
    """Regression: listar() still returns ALL tours regardless of activo state."""
    repo = SQLAServicioRepository(sf)
    s1 = Servicio(id=uuid.uuid4(), numero=30, nombre="Activo", activo=True)
    s2 = Servicio(id=uuid.uuid4(), numero=31, nombre="Inactivo", activo=False)
    repo.guardar(s1)
    repo.guardar(s2)
    todos = repo.listar()
    assert len(todos) == 2


# ── horarios round-trip (task 2.1) ────────────────────────────────────────────


def test_horarios_persiste_y_mantiene_orden(sf: sessionmaker[Session]) -> None:
    """Saving a Servicio with horarios and reloading returns the same list in order."""
    repo = SQLAServicioRepository(sf)
    s = Servicio(
        id=uuid.uuid4(),
        numero=50,
        nombre="Tour Con Horarios",
        horarios=["07:00", "19:00"],
    )
    repo.guardar(s)
    resultado = repo.buscar_por_id(s.id)
    assert resultado is not None
    assert resultado.horarios == ["07:00", "19:00"]


def test_horarios_vacio_persiste_como_lista_vacia(sf: sessionmaker[Session]) -> None:
    """Saving a Servicio without horarios returns an empty list on reload."""
    repo = SQLAServicioRepository(sf)
    s = Servicio(id=uuid.uuid4(), numero=51, nombre="Sin Horarios")
    repo.guardar(s)
    resultado = repo.buscar_por_id(s.id)
    assert resultado is not None
    assert resultado.horarios == []


def test_horarios_listar_preserva_datos(sf: sessionmaker[Session]) -> None:
    """listar() also returns correct horarios for each entity."""
    repo = SQLAServicioRepository(sf)
    s = Servicio(
        id=uuid.uuid4(),
        numero=52,
        nombre="Tour Horarios Listar",
        horarios=["08:00", "14:00", "20:00"],
    )
    repo.guardar(s)
    lista = repo.listar()
    match = next((x for x in lista if x.id == s.id), None)
    assert match is not None
    assert match.horarios == ["08:00", "14:00", "20:00"]
