"""Tests for the dev-only /nueva_propuesta conversation (MVP walking skeleton)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from telegram.ext import ConversationHandler

from garay.dominio.propuestas.contexto import PropuestaContexto
from garay.infraestructura.telegram.handlers_propuestas import (
    PROP_EMPRESA,
    cmd_nueva_propuesta,
    handle_prop_empresa,
)


async def test_cmd_pide_nombre_empresa_y_abre_estado() -> None:
    update = MagicMock()
    update.effective_user = MagicMock(id=1)
    update.effective_message = AsyncMock()
    with patch("garay.infraestructura.telegram.auth._es_dev", return_value=True):
        result = await cmd_nueva_propuesta(update, MagicMock())
    assert result == PROP_EMPRESA
    update.effective_message.reply_text.assert_called_once()


async def test_cmd_no_dev_no_abre_estado() -> None:
    update = MagicMock()
    update.effective_user = MagicMock(id=999)
    update.effective_message = AsyncMock()
    with patch("garay.infraestructura.telegram.auth._es_dev", return_value=False):
        result = await cmd_nueva_propuesta(update, MagicMock())
    assert result == ConversationHandler.END


async def test_handle_genera_y_envia_documento() -> None:
    service = MagicMock()
    service.generar.return_value = "<html>Acme</html>"
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "Acme S.A.S."
    context = MagicMock()
    context.bot_data = {"propuesta_audiovisual_service": service}

    result = await handle_prop_empresa(update, context)

    service.generar.assert_called_once_with(PropuestaContexto(empresa_nombre="Acme S.A.S."))
    update.effective_message.reply_document.assert_called_once()
    assert result == ConversationHandler.END


async def test_handle_texto_vacio_repregunta() -> None:
    service = MagicMock()
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "   "
    context = MagicMock()
    context.bot_data = {"propuesta_audiovisual_service": service}

    result = await handle_prop_empresa(update, context)

    service.generar.assert_not_called()
    update.effective_message.reply_document.assert_not_called()
    assert result == PROP_EMPRESA
