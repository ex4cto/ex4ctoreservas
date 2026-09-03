"""Tests for the dev-only /generar_documento multi-select flow (Slice 2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from telegram import InlineKeyboardMarkup
from telegram.ext import ConversationHandler

from garay.dominio.comun.dinero import Dinero
from garay.dominio.propuestas.contexto import PreciosAudiovisual, PropuestaContexto
from garay.infraestructura.telegram.handlers_propuestas import (
    GEN_EMPRESA,
    GEN_PRECIO_COMPLETO,
    GEN_PRECIO_MEDIO,
    GEN_PRECIOS,
    GEN_SELECCION,
    Documento,
    alternar_seleccion,
    cmd_generar_documento,
    construir_teclado,
    handle_gen_continuar,
    handle_gen_empresa,
    handle_gen_precios,
    handle_gen_toggle,
    handle_precio_completo,
    handle_precio_trafficker,
    parsear_precio,
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


async def test_empresa_pide_precios() -> None:
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "Acme S.A.S."
    context = MagicMock()
    context.user_data = {"gen_docs": {_AV}}

    result = await handle_gen_empresa(update, context)

    assert result == GEN_PRECIOS
    assert context.user_data["gen_empresa"] == "Acme S.A.S."
    assert "reply_markup" in update.effective_message.reply_text.call_args.kwargs


async def test_empresa_vacia_repregunta() -> None:
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "   "
    context = MagicMock()
    context.user_data = {"gen_docs": {_AV}}

    result = await handle_gen_empresa(update, context)

    assert result == GEN_EMPRESA


# --- precios ---------------------------------------------------------------


def test_parsear_precio_acepta_formatos() -> None:
    assert parsear_precio("3.000.000") == Dinero(3_000_000)
    assert parsear_precio("$1.800.000") == Dinero(1_800_000)
    assert parsear_precio("4500000") == Dinero(4_500_000)


def test_parsear_precio_rechaza_invalido() -> None:
    assert parsear_precio("abc") is None
    assert parsear_precio("") is None


async def test_precios_default_genera_con_defaults() -> None:
    service = MagicMock()
    service.generar.return_value = "<html/>"
    query = AsyncMock()
    query.data = "gen_precios:default"
    update = MagicMock()
    update.callback_query = query
    update.effective_message = AsyncMock()
    context = MagicMock()
    context.user_data = {"gen_empresa": "Acme"}
    context.bot_data = {"propuesta_audiovisual_service": service}

    result = await handle_gen_precios(update, context)

    service.generar.assert_called_once_with(PropuestaContexto(empresa_nombre="Acme"))
    update.effective_message.reply_document.assert_called_once()
    assert result == ConversationHandler.END


async def test_precios_editar_pide_primer_precio() -> None:
    query = AsyncMock()
    query.data = "gen_precios:editar"
    update = MagicMock()
    update.callback_query = query
    update.effective_message = AsyncMock()
    context = MagicMock()
    context.user_data = {"gen_empresa": "Acme"}

    result = await handle_gen_precios(update, context)

    assert result == GEN_PRECIO_COMPLETO
    update.effective_message.reply_text.assert_called_once()


async def test_precio_completo_valido_avanza() -> None:
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "4000000"
    context = MagicMock()
    context.user_data = {}

    result = await handle_precio_completo(update, context)

    assert context.user_data["gen_precio_completo"] == Dinero(4_000_000)
    assert result == GEN_PRECIO_MEDIO


async def test_precio_invalido_repregunta() -> None:
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "no soy número"
    context = MagicMock()
    context.user_data = {}

    result = await handle_precio_completo(update, context)

    assert "gen_precio_completo" not in context.user_data
    assert result == GEN_PRECIO_COMPLETO


async def test_precio_trafficker_construye_precios_custom_y_genera() -> None:
    service = MagicMock()
    service.generar.return_value = "<html/>"
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "800000"
    context = MagicMock()
    context.user_data = {
        "gen_empresa": "Acme",
        "gen_precio_completo": Dinero(4_000_000),
        "gen_precio_medio": Dinero(2_000_000),
        "gen_precio_community": Dinero(700_000),
    }
    context.bot_data = {"propuesta_audiovisual_service": service}

    result = await handle_precio_trafficker(update, context)

    esperado = PropuestaContexto(
        empresa_nombre="Acme",
        precios=PreciosAudiovisual(
            completo=Dinero(4_000_000),
            medio=Dinero(2_000_000),
            community=Dinero(700_000),
            trafficker=Dinero(800_000),
        ),
    )
    service.generar.assert_called_once_with(esperado)
    update.effective_message.reply_document.assert_called_once()
    assert result == ConversationHandler.END
