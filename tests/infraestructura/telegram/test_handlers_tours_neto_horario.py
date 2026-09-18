"""Tests for neto-por-horario editor in /editar_tour (states 242-243)."""

from __future__ import annotations

from garay.infraestructura.telegram.handlers_tours import (
    EDH_NETO_HOR_INGRESAR,
    EDH_NETO_HOR_SELECCIONAR,
    _CAMPOS_EDITABLES,
)
from garay.mensajes.catalogo import _CATALOGO


def test_neto_hor_state_constants_defined() -> None:
    assert EDH_NETO_HOR_SELECCIONAR == 242
    assert EDH_NETO_HOR_INGRESAR == 243


def test_neto_por_horario_in_campos_editables() -> None:
    campos = [k for k, _ in _CAMPOS_EDITABLES]
    assert "neto_por_horario" in campos


def test_catalog_keys_exist() -> None:
    assert "tour_neto_hor_titulo" in _CATALOGO
    assert "tour_neto_hor_ingrese" in _CATALOGO
    assert "tour_neto_hor_guardado" in _CATALOGO
    assert "tour_neto_hor_sin_horarios" in _CATALOGO
