"""Tests for the requiere_dev_conv guard — dev-only ConversationHandler entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.auth import requiere_dev_conv
from garay.mensajes.catalogo import obtener_mensaje


class TestRequiereDevConv:
    """requiere_dev_conv allows ONLY developers; returns END on any deny."""

    async def test_sin_usuario_retorna_end(self) -> None:
        @requiere_dev_conv
        async def handler(update: object, context: object) -> int:
            return 99

        update = MagicMock()
        update.effective_user = None
        result = await handler(update, MagicMock())
        assert result == ConversationHandler.END

    async def test_dev_llama_handler(self) -> None:
        @requiere_dev_conv
        async def handler(update: object, context: object) -> int:
            return 42

        update = MagicMock()
        update.effective_user = MagicMock(id=123)
        with patch("garay.infraestructura.telegram.auth._es_dev", return_value=True):
            result = await handler(update, MagicMock())
        assert result == 42

    async def test_no_dev_retorna_end_y_avisa(self) -> None:
        @requiere_dev_conv
        async def handler(update: object, context: object) -> int:
            return 42

        update = MagicMock()
        update.effective_user = MagicMock(id=999)
        update.effective_message = AsyncMock()
        with patch("garay.infraestructura.telegram.auth._es_dev", return_value=False):
            result = await handler(update, MagicMock())
        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called_once_with(
            obtener_mensaje("solo_desarrolladores")
        )
