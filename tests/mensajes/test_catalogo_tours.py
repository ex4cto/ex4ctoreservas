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
    # /nuevo_tour keys (Fase 2 PR 1)
    "tour_creado_ok",
    "tour_nombre_duplicado",
    "tour_pide_nombre",
    "tour_pide_neto_adulto",
    "tour_pide_neto_nino",
    "tour_nuevo_ficha",
]


class TestClavesTours:
    """All tour management message keys must exist in the catalog."""

    @pytest.mark.parametrize("clave", _TOUR_KEYS)
    def test_clave_existe(self, clave: str) -> None:
        msg = obtener_mensaje(clave)
        assert isinstance(msg, str)
        assert len(msg) > 0


class TestClavesNuevoTourFormato:
    """Keys for /nuevo_tour must accept their documented format arguments."""

    def test_tour_creado_ok_acepta_nombre(self) -> None:
        msg = obtener_mensaje("tour_creado_ok").format(nombre="City Tour")
        assert "City Tour" in msg

    def test_tour_nombre_duplicado_acepta_nombre(self) -> None:
        msg = obtener_mensaje("tour_nombre_duplicado").format(nombre="City Tour")
        assert "City Tour" in msg

    def test_tour_nuevo_ficha_acepta_todos_los_campos(self) -> None:
        msg = obtener_mensaje("tour_nuevo_ficha").format(
            familia="PLAYERO",
            nombre="City Tour",
            neto_adulto="100.000",
            neto_nino="—",
        )
        assert "PLAYERO" in msg
        assert "City Tour" in msg
