"""Tests for SQLACategoriaEgresoRepository — RED phase."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.conciliacion.entidades import CategoriaEgreso
from garay.infraestructura.persistencia.repositorios.categorias_egreso import (
    SQLACategoriaEgresoRepository,
)


def _cat(nombre: str, orden: int, activo: bool = True) -> CategoriaEgreso:
    return CategoriaEgreso(
        nombre=nombre,
        descripcion=f"Descripcion de {nombre}",
        activo=activo,
        orden=orden,
    )


def test_guardar_y_listar_activas(sf: sessionmaker[Session]) -> None:
    repo = SQLACategoriaEgresoRepository(sf)
    repo.guardar(_cat("arriendo", 1))
    repo.guardar(_cat("nomina", 2))

    activas = repo.listar_activas()
    assert "arriendo" in activas
    assert "nomina" in activas


def test_listar_activas_excluye_inactivas(sf: sessionmaker[Session]) -> None:
    repo = SQLACategoriaEgresoRepository(sf)
    repo.guardar(_cat("activa", 1, activo=True))
    repo.guardar(_cat("inactiva", 2, activo=False))

    activas = repo.listar_activas()
    assert "activa" in activas
    assert "inactiva" not in activas


def test_listar_activas_ordenadas_por_orden(sf: sessionmaker[Session]) -> None:
    repo = SQLACategoriaEgresoRepository(sf)
    repo.guardar(_cat("tercera", 3))
    repo.guardar(_cat("primera", 1))
    repo.guardar(_cat("segunda", 2))

    activas = repo.listar_activas()
    assert activas == ["primera", "segunda", "tercera"]


def test_guardar_es_idempotente(sf: sessionmaker[Session]) -> None:
    repo = SQLACategoriaEgresoRepository(sf)
    cat = _cat("arriendo", 1)
    repo.guardar(cat)
    # Update and re-save
    cat2 = CategoriaEgreso(
        nombre="arriendo", descripcion="Arriendo actualizado", activo=True, orden=1
    )
    repo.guardar(cat2)

    activas = repo.listar_activas()
    assert activas.count("arriendo") == 1


def test_listar_activas_vacio(sf: sessionmaker[Session]) -> None:
    repo = SQLACategoriaEgresoRepository(sf)
    assert repo.listar_activas() == []
