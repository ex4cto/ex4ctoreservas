"""Tests for the GV editar-metodo-pago handler (infrastructure layer)."""

from __future__ import annotations

import re

import pytest

from garay.infraestructura.telegram.handlers_gestion_ventas import (
    GV_EDIT_CAMPO_PATTERN,
    GV_EDIT_METODO_PAGO,
    GV_EDIT_METODO_PAGO_PATTERN,
    GV_EDIT_TOUR_VALOR,
    _construir_teclado_campos,
)


class TestTecladoCamposContieneBotones:
    def test_campo_metodo_pago_button_presente(self) -> None:
        """campo_metodo_pago button must appear in the field picker keyboard."""
        keyboard = _construir_teclado_campos(es_admin=False)
        callback_data_vals = [
            btn.callback_data
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        assert "gv_campo:metodo_pago" in callback_data_vals

    def test_campo_metodo_pago_button_presente_admin(self) -> None:
        """campo_metodo_pago button also appears when es_admin=True."""
        keyboard = _construir_teclado_campos(es_admin=True)
        callback_data_vals = [
            btn.callback_data
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        assert "gv_campo:metodo_pago" in callback_data_vals


class TestPatterns:
    def test_gv_campo_metodo_pago_matches_edit_campo_pattern(self) -> None:
        """gv_campo:metodo_pago must match GV_EDIT_CAMPO_PATTERN."""
        assert re.match(GV_EDIT_CAMPO_PATTERN, "gv_campo:metodo_pago")

    def test_gv_metodo_pago_transferencia_matches_pattern(self) -> None:
        """gv_metodo_pago:TRANSFERENCIA must match GV_EDIT_METODO_PAGO_PATTERN."""
        assert re.match(GV_EDIT_METODO_PAGO_PATTERN, "gv_metodo_pago:TRANSFERENCIA")

    def test_gv_metodo_pago_efectivo_matches_pattern(self) -> None:
        """gv_metodo_pago:EFECTIVO must match GV_EDIT_METODO_PAGO_PATTERN."""
        assert re.match(GV_EDIT_METODO_PAGO_PATTERN, "gv_metodo_pago:EFECTIVO")

    def test_gv_metodo_pago_tarjeta_matches_pattern(self) -> None:
        """gv_metodo_pago:TARJETA must match GV_EDIT_METODO_PAGO_PATTERN."""
        assert re.match(GV_EDIT_METODO_PAGO_PATTERN, "gv_metodo_pago:TARJETA")

    def test_gv_volver_detalle_matches_metodo_pago_pattern(self) -> None:
        """gv_volver_detalle must match GV_EDIT_METODO_PAGO_PATTERN (back button)."""
        assert re.match(GV_EDIT_METODO_PAGO_PATTERN, "gv_volver_detalle")

    def test_invalid_does_not_match_metodo_pago_pattern(self) -> None:
        """Random string must NOT match GV_EDIT_METODO_PAGO_PATTERN."""
        assert not re.match(GV_EDIT_METODO_PAGO_PATTERN, "gv_campo:nombre")


class TestStateUniqueness:
    def test_gv_edit_metodo_pago_state_is_237(self) -> None:
        """GV_EDIT_METODO_PAGO must equal 237."""
        assert GV_EDIT_METODO_PAGO == 237

    def test_gv_edit_metodo_pago_not_equal_to_tour_valor(self) -> None:
        """GV_EDIT_METODO_PAGO must not conflict with GV_EDIT_TOUR_VALOR (236)."""
        assert GV_EDIT_METODO_PAGO != GV_EDIT_TOUR_VALOR
