"""Tests for the leftover-keyboard tracking helpers (no hanging buttons)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.infraestructura.telegram.handlers import (
    _limpiar_teclado_recordado,
    recordar_teclado,
)


def test_recordar_teclado_guarda_chat_y_mensaje() -> None:
    ctx = MagicMock()
    ctx.user_data = {}
    msg = MagicMock()
    msg.chat_id = 55
    msg.message_id = 77
    recordar_teclado(ctx, msg)
    assert ctx.user_data["_ultimo_teclado"] == (55, 77)


@pytest.mark.asyncio
async def test_limpiar_quita_botones_y_popea_la_ref() -> None:
    ctx = MagicMock()
    ctx.user_data = {"_ultimo_teclado": (55, 77)}
    ctx.bot = AsyncMock()
    await _limpiar_teclado_recordado(ctx)
    ctx.bot.edit_message_reply_markup.assert_called_once()
    kwargs = ctx.bot.edit_message_reply_markup.call_args.kwargs
    assert kwargs["chat_id"] == 55
    assert kwargs["message_id"] == 77
    assert kwargs["reply_markup"] is None
    assert "_ultimo_teclado" not in ctx.user_data


@pytest.mark.asyncio
async def test_limpiar_sin_ref_no_llama_al_bot() -> None:
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = AsyncMock()
    await _limpiar_teclado_recordado(ctx)
    ctx.bot.edit_message_reply_markup.assert_not_called()
