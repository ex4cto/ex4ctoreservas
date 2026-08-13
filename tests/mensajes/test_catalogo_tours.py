"""Tests for tour management message keys in the centralized catalog."""

from __future__ import annotations

import pytest

from garay.mensajes.catalogo import obtener_mensaje

_TOUR_KEYS = [
    "tour_selecciona_familia",
    "tour_selecciona_tour",
    "tour_ficha",
    "tour_editar_campo",
    "tour_confirmar_cambio",
    "tour_campo_sin_cambio",
    "tour_guardado_ok",
    "tour_desactivado_ok",
    "tour_eliminar_confirmar",
    "tour_eliminado_ok",
    "tour_cancelado",
    "tour_neto_invalido",
    "tour_nombre_vacio",
    "tour_nueva_familia_prompt",
]


class TestClavesTours:
    """All tour management message keys must exist in the catalog."""

    @pytest.mark.parametrize("clave", _TOUR_KEYS)
    def test_clave_existe(self, clave: str) -> None:
        msg = obtener_mensaje(clave)
        assert isinstance(msg, str)
        assert len(msg) > 0
