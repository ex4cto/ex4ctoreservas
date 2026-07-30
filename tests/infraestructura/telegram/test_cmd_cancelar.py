"""Tests for /cancelar handlers — standalone (no active conversation) and flag mechanics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.infraestructura.telegram.handlers import cmd_cancelar, cmd_cancelar_sin_conv
from garay.mensajes.catalogo import obtener_mensaje


def _make_update(*, message: bool = True) -> MagicMock:
    update = MagicMock()
    update.effective_message = AsyncMock()
    if message:
        update.message = MagicMock()
    else:
        update.message = None
    update.callback_query = None
    return update


def _make_context(user_data: dict | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot_data = {}
    return ctx


class TestCmdCancelarSinConv:
    @pytest.mark.asyncio
    async def test_standalone_sin_flag_envia_mensaje_sin_operacion(self) -> None:
        """When no conversation was handled, reply with the 'no active operation' message."""
        update = _make_update()
        ctx = _make_context(user_data={})

        await cmd_cancelar_sin_conv(update, ctx)

        expected = obtener_mensaje("cancelar_sin_operacion")
        update.effective_message.reply_text.assert_called_once_with(expected)

    @pytest.mark.asyncio
    async def test_standalone_con_flag_previo_no_responde(self) -> None:
        """When _cancelar_handled is True, do NOT send any message."""
        update = _make_update()
        ctx = _make_context(user_data={"_cancelar_handled": True})

        await cmd_cancelar_sin_conv(update, ctx)

        update.effective_message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_standalone_limpia_flag_despues_de_ejecutarse(self) -> None:
        """After cmd_cancelar_sin_conv runs, the flag must be removed from user_data."""
        update = _make_update()
        ctx = _make_context(user_data={"_cancelar_handled": True})

        await cmd_cancelar_sin_conv(update, ctx)

        assert "_cancelar_handled" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_cmd_cancelar_setea_flag_en_user_data(self) -> None:
        """cmd_cancelar must set _cancelar_handled=True even when fsm is None."""
        update = _make_update()
        ctx = _make_context(user_data={})

        with patch(
            "garay.infraestructura.telegram.handlers._get_fsm",
            return_value=None,
        ):
            await cmd_cancelar(update, ctx)

        assert ctx.user_data.get("_cancelar_handled") is True

    @pytest.mark.asyncio
    async def test_standalone_usa_effective_message_no_message_directo(self) -> None:
        """cmd_cancelar_sin_conv uses effective_message, not message — survives None message."""
        update = _make_update(message=False)
        assert update.message is None
        ctx = _make_context(user_data={})

        # Must not raise AttributeError and must call effective_message.reply_text
        await cmd_cancelar_sin_conv(update, ctx)

        update.effective_message.reply_text.assert_called_once()
