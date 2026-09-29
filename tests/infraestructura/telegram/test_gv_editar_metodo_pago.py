"""Tests for the GV editar-metodo-pago handler (infrastructure layer)."""

from __future__ import annotations

import re
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.infraestructura.telegram.handlers_gestion_ventas import (
    GV_EDIT_CAMPO_PATTERN,
    GV_EDIT_METODO_PAGO,
    GV_EDIT_METODO_PAGO_PATTERN,
    GV_EDIT_TOUR_VALOR,
    _construir_teclado_campos,
)

# ---------------------------------------------------------------------------
# Helpers for confirmation-handler tests
# ---------------------------------------------------------------------------


def _make_venta_mp(mensaje_grupo_id: int | None = 42000) -> MagicMock:
    v = MagicMock()
    v.id = uuid.uuid4()
    v.mensaje_grupo_id = mensaje_grupo_id
    return v


def _make_update_mp(callback_data: str) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_message = AsyncMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = callback_data
    update.callback_query.from_user = MagicMock()
    update.callback_query.from_user.id = 123
    update.message = None
    return update


def _make_context_mp(
    venta: MagicMock | None = None,
    service: MagicMock | None = None,
    include_venta_repo: bool = True,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = AsyncMock()
    ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    ctx.bot.delete_message = AsyncMock()

    _venta = venta or _make_venta_mp()

    venta_repo = MagicMock()
    venta_repo.buscar_por_id.return_value = _venta

    freelancer_repo = MagicMock()
    freelancer_repo.buscar_por_telegram_id.return_value = MagicMock(nombre="Admin")

    socios_config_repo = MagicMock()
    socios_config_repo.listar.return_value = []

    notificador = MagicMock()

    ctx.bot_data = {
        "freelancer_repo": freelancer_repo,
        "socios_config_repo": socios_config_repo,
        "grupo_id": "-1001234567",
        "notificador": notificador,
        "editar_metodo_pago_venta_service": service or MagicMock(),
    }
    if include_venta_repo:
        ctx.bot_data["venta_repo"] = venta_repo

    return ctx


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


# ---------------------------------------------------------------------------
# Confirmation-handler integration tests
# ---------------------------------------------------------------------------


class TestHandleConfirmarEditarMetodoPago:
    @pytest.mark.asyncio
    async def test_service_success_sends_group_message(self) -> None:
        """After confirming metodo_pago edit, send_message must be called for the sales group."""
        from garay.dominio.comun.tipos import MetodoPago
        from garay.infraestructura.telegram.handlers_gestion_ventas import handle_gv_confirmar

        venta_id = uuid.uuid4()
        venta = _make_venta_mp(mensaje_grupo_id=42000)
        ctx = _make_context_mp(venta=venta)
        ctx.user_data.update(
            {
                "gv_accion": "editar_metodo_pago",
                "gv_venta_id": str(venta_id),
                "gv_motivo": "El cliente cambió su forma de pago",
                "gv_nuevo_metodo_pago": MetodoPago.TRANSFERENCIA,
                "gv_metodo_pago_anterior": "EFECTIVO",
                "gv_cliente_nombre": "Ana García",
                "gv_tours": "Isla del Rosario",
            }
        )
        update = _make_update_mp("gv_confirmar")

        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.obtener_settings",
            return_value=MagicMock(propietario_telegram_ids=""),
        ):
            await handle_gv_confirmar(update, ctx)

        group_calls = [
            c
            for c in ctx.bot.send_message.call_args_list
            if c.kwargs.get("chat_id") == "-1001234567"
        ]
        assert group_calls, "send_message was not called for the sales group"
        text = group_calls[0].kwargs.get("text", "")
        assert "Método de pago" in text

    @pytest.mark.asyncio
    async def test_group_notified_via_fallback_when_venta_repo_missing(self) -> None:
        """When venta_repo is absent (venta=None), notificador must send the group message."""
        from garay.dominio.comun.tipos import MetodoPago
        from garay.infraestructura.telegram.handlers_gestion_ventas import handle_gv_confirmar

        venta_id = uuid.uuid4()
        ctx = _make_context_mp(include_venta_repo=False)
        ctx.user_data.update(
            {
                "gv_accion": "editar_metodo_pago",
                "gv_venta_id": str(venta_id),
                "gv_motivo": "Cambio de método",
                "gv_nuevo_metodo_pago": MetodoPago.EFECTIVO,
                "gv_metodo_pago_anterior": "TRANSFERENCIA",
                "gv_cliente_nombre": "Carlos",
                "gv_tours": "Tour Ciudad",
            }
        )
        update = _make_update_mp("gv_confirmar")

        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.obtener_settings",
            return_value=MagicMock(propietario_telegram_ids=""),
        ):
            await handle_gv_confirmar(update, ctx)

        ctx.bot_data["notificador"].notificar.assert_called_once()
