"""Tests for the dev-only /generar_documento multi-select flow (Slice 2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from telegram import InlineKeyboardMarkup
from telegram.ext import ConversationHandler

from garay.dominio.propuestas.contexto import PropuestaContexto
from garay.infraestructura.telegram.handlers_propuestas import (
    GEN_EMPRESA,
    GEN_SELECCION,
    Documento,
    alternar_seleccion,
    cmd_generar_documento,
    construir_teclado,
    handle_gen_continuar,
    handle_gen_empresa,
    handle_gen_toggle,
)

_AV = Documento.PROPUESTA_AUDIOVISUAL.value


# --- pure helpers -----------------------------------------------------------


def test_alternar_agrega_y_quita() -> None:
    assert alternar_seleccion(set(), _AV) == {_AV}
    assert alternar_seleccion({_AV}, _AV) == set()


def test_teclado_marca_seleccionados() -> None:
    kb = construir_teclado({_AV})
    assert isinstance(kb, InlineKeyboardMarkup)
    textos = [b.text for fila in kb.inline_keyboard for b in fila]
    assert any("✅" in t for t in textos)
    assert any("🔒" in t for t in textos)  # docs no implementados
    assert any("Continuar" in t for t in textos)


def test_teclado_sin_seleccion_no_tiene_check() -> None:
    kb = construir_teclado(set())
    textos = [b.text for fila in kb.inline_keyboard for b in fila]
    assert not any("✅" in t for t in textos)


# --- entry point ------------------------------------------------------------


async def test_cmd_abre_menu_seleccion() -> None:
    update = MagicMock()
    update.effective_user = MagicMock(id=1)
    update.effective_message = AsyncMock()
    context = MagicMock()
    context.user_data = {}
    with patch("garay.infraestructura.telegram.auth._es_dev", return_value=True):
        result = await cmd_generar_documento(update, context)
    assert result == GEN_SELECCION
    update.effective_message.reply_text.assert_called_once()
    # menu shown with an inline keyboard
    assert "reply_markup" in update.effective_message.reply_text.call_args.kwargs


async def test_cmd_no_dev_termina() -> None:
    update = MagicMock()
    update.effective_user = MagicMock(id=999)
    update.effective_message = AsyncMock()
    with patch("garay.infraestructura.telegram.auth._es_dev", return_value=False):
        result = await cmd_generar_documento(update, MagicMock())
    assert result == ConversationHandler.END


# --- toggle -----------------------------------------------------------------


async def test_toggle_documento_implementado_selecciona() -> None:
    query = AsyncMock()
    query.data = f"gen_toggle:{_AV}"
    update = MagicMock()
    update.callback_query = query
    context = MagicMock()
    context.user_data = {"gen_docs": set()}

    result = await handle_gen_toggle(update, context)

    assert context.user_data["gen_docs"] == {_AV}
    query.edit_message_reply_markup.assert_called_once()
    assert result == GEN_SELECCION


async def test_toggle_documento_no_implementado_avisa_proximamente() -> None:
    query = AsyncMock()
    query.data = f"gen_toggle:{Documento.PROPUESTA_SOFTWARE.value}"
    update = MagicMock()
    update.callback_query = query
    context = MagicMock()
    context.user_data = {"gen_docs": set()}

    result = await handle_gen_toggle(update, context)

    assert context.user_data["gen_docs"] == set()
    query.edit_message_reply_markup.assert_not_called()
    query.answer.assert_called_once()
    assert result == GEN_SELECCION


# --- continuar --------------------------------------------------------------


async def test_continuar_sin_seleccion_se_queda() -> None:
    query = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    context = MagicMock()
    context.user_data = {"gen_docs": set()}

    result = await handle_gen_continuar(update, context)

    assert result == GEN_SELECCION
    query.answer.assert_called_once()


async def test_continuar_con_seleccion_pide_empresa() -> None:
    query = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_message = AsyncMock()
    context = MagicMock()
    context.user_data = {"gen_docs": {_AV}}

    result = await handle_gen_continuar(update, context)

    assert result == GEN_EMPRESA
    update.effective_message.reply_text.assert_called_once()


# --- empresa → genera -------------------------------------------------------


async def test_empresa_genera_y_envia_audiovisual() -> None:
    service = MagicMock()
    service.generar.return_value = "<html>Acme</html>"
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "Acme S.A.S."
    context = MagicMock()
    context.user_data = {"gen_docs": {_AV}}
    context.bot_data = {"propuesta_audiovisual_service": service}

    result = await handle_gen_empresa(update, context)

    service.generar.assert_called_once_with(PropuestaContexto(empresa_nombre="Acme S.A.S."))
    update.effective_message.reply_document.assert_called_once()
    assert result == ConversationHandler.END


async def test_empresa_vacia_repregunta() -> None:
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "   "
    context = MagicMock()
    context.user_data = {"gen_docs": {_AV}}
    context.bot_data = {"propuesta_audiovisual_service": MagicMock()}

    result = await handle_gen_empresa(update, context)

    update.effective_message.reply_document.assert_not_called()
    assert result == GEN_EMPRESA
