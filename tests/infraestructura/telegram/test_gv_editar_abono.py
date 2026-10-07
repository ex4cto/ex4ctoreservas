"""Tests for the GV editar-abono handler (infrastructure layer)."""

from __future__ import annotations

import re
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.infraestructura.telegram.handlers_gestion_ventas import (
    GV_EDIT_ABONO,
    GV_EDIT_CAMPO_PATTERN,
    GV_MOTIVO,
    _construir_teclado_campos,
)


def _make_venta_ab(
    abono: Dinero | None = None,
    valor_venta: Dinero | None = None,
    mensaje_grupo_id: int | None = 42000,
) -> MagicMock:
    v = MagicMock()
    v.id = uuid.uuid4()
    v.abono = abono
    v.valor_venta = valor_venta or Dinero(300_000)
    v.mensaje_grupo_id = mensaje_grupo_id
    return v


def _make_update_text(text: str) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_message = AsyncMock()
    update.callback_query = None
    update.message = MagicMock()
    update.message.text = text
    return update


def _make_context_ab(
    venta: MagicMock | None = None,
    service: MagicMock | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = AsyncMock()
    ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    ctx.bot.delete_message = AsyncMock()

    _venta = venta or _make_venta_ab()

    venta_repo = MagicMock()
    venta_repo.buscar_por_id.return_value = _venta

    freelancer_repo = MagicMock()
    freelancer_repo.buscar_por_telegram_id.return_value = MagicMock(nombre="Admin")

    socios_config_repo = MagicMock()
    socios_config_repo.listar.return_value = []

    ctx.bot_data = {
        "venta_repo": venta_repo,
        "freelancer_repo": freelancer_repo,
        "socios_config_repo": socios_config_repo,
        "grupo_id": "-1001234567",
        "notificador": MagicMock(),
        "editar_abono_venta_service": service or MagicMock(),
    }
    return ctx


# ---------------------------------------------------------------------------
# Keyboard / pattern tests
# ---------------------------------------------------------------------------


class TestTecladoCamposBotonAbono:
    def test_abono_button_ausente_para_no_admin(self) -> None:
        keyboard = _construir_teclado_campos(es_admin=False)
        callback_data_vals = [
            btn.callback_data
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        assert "gv_campo:abono" not in callback_data_vals

    def test_abono_button_presente_para_admin(self) -> None:
        keyboard = _construir_teclado_campos(es_admin=True)
        callback_data_vals = [
            btn.callback_data
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        assert "gv_campo:abono" in callback_data_vals


class TestPatterns:
    def test_gv_campo_abono_matches_edit_campo_pattern(self) -> None:
        assert re.match(GV_EDIT_CAMPO_PATTERN, "gv_campo:abono")


class TestStateUniqueness:
    def test_gv_edit_abono_state_is_238(self) -> None:
        assert GV_EDIT_ABONO == 238


# ---------------------------------------------------------------------------
# handle_gv_edit_abono: text input → GV_MOTIVO
# ---------------------------------------------------------------------------


class TestHandleGvEditAbono:
    @pytest.mark.asyncio
    async def test_valid_amount_stores_and_returns_gv_motivo(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import handle_gv_edit_abono

        venta = _make_venta_ab(abono=Dinero(50_000))
        ctx = _make_context_ab(venta=venta)
        ctx.user_data["gv_venta_id"] = str(venta.id)

        update = _make_update_text("80000")
        result = await handle_gv_edit_abono(update, ctx)

        assert result == GV_MOTIVO
        assert ctx.user_data.get("gv_nuevo_abono") == Dinero(80_000)

    @pytest.mark.asyncio
    async def test_zero_clears_abono_stores_none(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import handle_gv_edit_abono

        venta = _make_venta_ab(abono=Dinero(50_000))
        ctx = _make_context_ab(venta=venta)
        ctx.user_data["gv_venta_id"] = str(venta.id)

        update = _make_update_text("0")
        result = await handle_gv_edit_abono(update, ctx)

        assert result == GV_MOTIVO
        assert ctx.user_data.get("gv_nuevo_abono") is None

    @pytest.mark.asyncio
    async def test_invalid_text_stays_in_gv_edit_abono(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            GV_EDIT_ABONO,
            handle_gv_edit_abono,
        )

        ctx = _make_context_ab()
        update = _make_update_text("no es un número")
        result = await handle_gv_edit_abono(update, ctx)

        assert result == GV_EDIT_ABONO


# ---------------------------------------------------------------------------
# Confirmation handler
# ---------------------------------------------------------------------------


class TestHandleConfirmarEditarAbono:
    @pytest.mark.asyncio
    async def test_service_success_sends_group_message(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import handle_gv_confirmar

        venta_id = uuid.uuid4()
        venta = _make_venta_ab(mensaje_grupo_id=42000)
        ctx = _make_context_ab(venta=venta)
        ctx.user_data.update(
            {
                "gv_accion": "editar_abono",
                "gv_venta_id": str(venta_id),
                "gv_motivo": "Cliente pagó abono",
                "gv_nuevo_abono": Dinero(80_000),
                "gv_abono_anterior": "$50.000",
                "gv_cliente_nombre": "Ana García",
                "gv_tours": "Isla del Rosario",
            }
        )

        update = MagicMock()
        update.callback_query = AsyncMock()
        update.callback_query.data = "gv_confirmar"
        update.effective_user = MagicMock()
        update.effective_user.id = 123
        update.effective_message = AsyncMock()
        update.message = None

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
        assert "Abono" in text
