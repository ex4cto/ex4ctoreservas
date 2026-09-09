"""Tests for GestionarCategoriasService — RED phase (TDD)."""

from __future__ import annotations

import pytest

from garay.aplicacion.egresos.gestionar_categorias import GestionarCategoriasService
from garay.dominio.conciliacion.entidades import CategoriaEgreso
from garay.dominio.conciliacion.errores import (
    CategoriaEgresoDuplicada,
    CategoriaEgresoProtegida,
)
from garay.dominio.puertos.repositorios import CategoriaEgresoRepository


class _FakeCategoriaRepo(CategoriaEgresoRepository):
    """In-memory fake that fully satisfies the port (keyed by nombre)."""

    def __init__(self) -> None:
        self._items: dict[str, CategoriaEgreso] = {}

    def _ordenadas(self) -> list[CategoriaEgreso]:
        return sorted(self._items.values(), key=lambda c: (c.orden, c.nombre))

    def listar_activas(self) -> list[str]:
        return [c.nombre for c in self._ordenadas() if c.activo]

    def listar_todas(self) -> list[CategoriaEgreso]:
        return self._ordenadas()

    def guardar(self, categoria: CategoriaEgreso) -> None:
        self._items[categoria.nombre] = categoria


def _seed(repo: _FakeCategoriaRepo, *nombres: str) -> None:
    for i, nombre in enumerate(nombres, start=1):
        repo.guardar(CategoriaEgreso(nombre=nombre, descripcion="", activo=True, orden=i))


def _make_service() -> tuple[GestionarCategoriasService, _FakeCategoriaRepo]:
    repo = _FakeCategoriaRepo()
    return GestionarCategoriasService(repo), repo


class TestListar:
    def test_listar_todas_delega_al_repo(self) -> None:
        service, repo = _make_service()
        _seed(repo, "comisiones", "marketing")
        assert [c.nombre for c in service.listar_todas()] == ["comisiones", "marketing"]


class TestCrear:
    def test_crear_agrega_con_orden_siguiente(self) -> None:
        service, repo = _make_service()
        _seed(repo, "comisiones", "marketing")  # ordenes 1, 2
        creada = service.crear("papelería")
        assert creada.nombre == "papelería"
        assert creada.activo is True
        assert creada.orden == 3
        assert "papelería" in [c.nombre for c in repo.listar_todas()]

    def test_crear_normaliza_espacios(self) -> None:
        service, _ = _make_service()
        creada = service.crear("  proveedores   tour  ")
        assert creada.nombre == "proveedores tour"

    def test_crear_duplicada_lanza(self) -> None:
        service, repo = _make_service()
        _seed(repo, "comisiones")
        with pytest.raises(CategoriaEgresoDuplicada):
            service.crear("Comisiones")

    def test_crear_duplicada_ignora_acentos(self) -> None:
        service, repo = _make_service()
        _seed(repo, "alimentación")
        with pytest.raises(CategoriaEgresoDuplicada):
            service.crear("alimentacion")

    def test_crear_nombre_vacio_lanza(self) -> None:
        service, _ = _make_service()
        with pytest.raises(ValueError):
            service.crear("   ")

    def test_crear_primera_categoria_orden_uno(self) -> None:
        service, _ = _make_service()
        creada = service.crear("software")
        assert creada.orden == 1


class TestSugerirParecida:
    def test_sugiere_parecida(self) -> None:
        service, repo = _make_service()
        _seed(repo, "papelería", "marketing")
        assert service.sugerir_parecida("papleria") == "papelería"

    def test_sin_parecido_retorna_none(self) -> None:
        service, repo = _make_service()
        _seed(repo, "comisiones")
        assert service.sugerir_parecida("software") is None


class TestActivarDesactivar:
    def test_desactivar_marca_inactiva(self) -> None:
        service, repo = _make_service()
        _seed(repo, "marketing")
        service.desactivar("marketing")
        assert "marketing" not in repo.listar_activas()
        assert "marketing" in [c.nombre for c in repo.listar_todas()]

    def test_desactivar_protegida_lanza(self) -> None:
        service, repo = _make_service()
        _seed(repo, "transporte")
        with pytest.raises(CategoriaEgresoProtegida):
            service.desactivar("transporte")

    def test_desactivar_otro_protegida_lanza(self) -> None:
        service, repo = _make_service()
        _seed(repo, "otro")
        with pytest.raises(CategoriaEgresoProtegida):
            service.desactivar("otro")

    def test_activar_marca_activa(self) -> None:
        service, repo = _make_service()
        repo.guardar(
            CategoriaEgreso(nombre="marketing", descripcion="", activo=False, orden=1)
        )
        service.activar("marketing")
        assert "marketing" in repo.listar_activas()

    def test_desactivar_categoria_inexistente_lanza(self) -> None:
        service, _ = _make_service()
        with pytest.raises(ValueError):
            service.desactivar("no_existe")


class TestEditarDescripcion:
    def test_editar_descripcion_actualiza(self) -> None:
        service, repo = _make_service()
        _seed(repo, "marketing")
        service.editar_descripcion("marketing", "Publicidad y redes")
        cat = next(c for c in repo.listar_todas() if c.nombre == "marketing")
        assert cat.descripcion == "Publicidad y redes"
        assert cat.activo is True  # no altera el estado
