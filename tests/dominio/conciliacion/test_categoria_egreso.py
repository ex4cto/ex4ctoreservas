"""Tests for CategoriaEgreso domain entity — RED phase."""

from __future__ import annotations

from garay.dominio.conciliacion.entidades import CategoriaEgreso


class TestCategoriaEgreso:
    def test_construccion_valida(self) -> None:
        cat = CategoriaEgreso(
            nombre="arriendo",
            descripcion="Arriendo de local",
            activo=True,
            orden=1,
        )
        assert cat.nombre == "arriendo"
        assert cat.descripcion == "Arriendo de local"
        assert cat.activo is True
        assert cat.orden == 1

    def test_construccion_inactiva(self) -> None:
        cat = CategoriaEgreso(
            nombre="obsoleta",
            descripcion="Categoria obsoleta",
            activo=False,
            orden=99,
        )
        assert cat.activo is False

    def test_orden_es_entero(self) -> None:
        cat = CategoriaEgreso(nombre="papeleria", descripcion="", activo=True, orden=4)
        assert isinstance(cat.orden, int)

    def test_descripcion_puede_ser_vacia(self) -> None:
        cat = CategoriaEgreso(nombre="otro", descripcion="", activo=True, orden=7)
        assert cat.descripcion == ""
