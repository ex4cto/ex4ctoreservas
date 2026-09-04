"""Tests for the dev-only /generar_documento multi-select flow (Slice 2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from telegram import InlineKeyboardMarkup
from telegram.ext import ConversationHandler

from garay.dominio.comun.dinero import Dinero
from garay.dominio.propuestas.contexto import (
    PreciosAudiovisual,
    PreciosSoftware,
    PropuestaContexto,
)
from garay.infraestructura.telegram.handlers_propuestas import (
    GEN_EJEMPLOS,
    GEN_EMPRESA,
    GEN_NIT,
    GEN_PLAN_CONTRATO,
    GEN_PRECIO_COMPLETO,
    GEN_PRECIO_MEDIO,
    GEN_PRECIOS,
    GEN_PRECIOS_SW,
    GEN_SELECCION,
    Documento,
    alternar_seleccion,
    cmd_generar_documento,
    construir_teclado,
    handle_ciudad,
    handle_ejemplos,
    handle_gen_continuar,
    handle_gen_empresa,
    handle_gen_precios,
    handle_gen_precios_sw,
    handle_gen_toggle,
    handle_plan_contrato,
    handle_precio_completo,
    handle_precio_trafficker,
    handle_razon_social,
    handle_sw_anual,
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
    assert any("Continuar" in t for t in textos)
    # los 4 documentos + Continuar
    assert len(textos) == 5


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


async def test_toggle_documento_desconocido_avisa_proximamente() -> None:
    query = AsyncMock()
    query.data = "gen_toggle:documento_inexistente"
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
    context.user_data = {"gen_empresa": "Acme", "gen_docs": {_AV}}
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
        "gen_docs": {_AV},
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


# --- software (Slice 4a) ----------------------------------------------------

_SW = Documento.PROPUESTA_SOFTWARE.value


async def test_empresa_con_software_pide_ejemplos() -> None:
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "Acme"
    context = MagicMock()
    context.user_data = {"gen_docs": {_SW}}

    result = await handle_gen_empresa(update, context)

    assert result == GEN_EJEMPLOS
    update.effective_message.reply_text.assert_called_once()


async def test_ejemplos_guarda_y_pide_precios_sw() -> None:
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "citas y consultas"
    context = MagicMock()
    context.user_data = {"gen_docs": {_SW}, "gen_empresa": "Acme"}

    result = await handle_ejemplos(update, context)

    assert context.user_data["gen_ejemplos"] == "citas y consultas"
    assert result == GEN_PRECIOS_SW


async def test_av_default_con_ambos_pasa_a_precios_sw() -> None:
    query = AsyncMock()
    query.data = "gen_precios:default"
    update = MagicMock()
    update.callback_query = query
    update.effective_message = AsyncMock()
    context = MagicMock()
    context.user_data = {"gen_empresa": "Acme", "gen_docs": {_AV, _SW}}

    result = await handle_gen_precios(update, context)

    assert result == GEN_PRECIOS_SW


async def test_precios_sw_default_genera() -> None:
    sw = MagicMock()
    sw.generar.return_value = "<s/>"
    query = AsyncMock()
    query.data = "gen_precios:default"
    update = MagicMock()
    update.callback_query = query
    update.effective_message = AsyncMock()
    context = MagicMock()
    context.user_data = {"gen_empresa": "Acme", "gen_docs": {_SW}}
    context.bot_data = {"propuesta_software_service": sw}

    result = await handle_gen_precios_sw(update, context)

    sw.generar.assert_called_once()
    update.effective_message.reply_document.assert_called_once()
    assert result == ConversationHandler.END


async def test_sw_anual_construye_precios_custom_y_genera() -> None:
    sw = MagicMock()
    sw.generar.return_value = "<s/>"
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "6000000"
    context = MagicMock()
    context.user_data = {
        "gen_empresa": "Acme",
        "gen_docs": {_SW},
        "gen_sw_desarrollo": Dinero(30_000_000),
        "gen_sw_impl": Dinero(3_000_000),
        "gen_sw_mensual": Dinero(600_000),
    }
    context.bot_data = {"propuesta_software_service": sw}

    result = await handle_sw_anual(update, context)

    esperado = PropuestaContexto(
        empresa_nombre="Acme",
        precios_software=PreciosSoftware(
            desarrollo=Dinero(30_000_000),
            implementacion=Dinero(3_000_000),
            mensual=Dinero(600_000),
            anual=Dinero(6_000_000),
        ),
    )
    sw.generar.assert_called_once_with(esperado)
    assert result == ConversationHandler.END


# --- contratos (Slice 5b) ---------------------------------------------------

_CAV = Documento.CONTRATO_AUDIOVISUAL.value
_CSW = Documento.CONTRATO_SOFTWARE.value

_LEGAL = {
    "gen_razon_social": "Clinica Sonrisa SAS",
    "gen_nit": "900123456-7",
    "gen_rep_legal": "Ana Perez",
    "gen_rep_cc": "43111222",
    "gen_direccion": "Cra 1 #2-3",
    "gen_ciudad": "Medellin",
}


async def test_razon_social_avanza_a_nit() -> None:
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "Clinica Sonrisa SAS"
    context = MagicMock()
    context.user_data = {"gen_docs": {_CSW}}

    result = await handle_razon_social(update, context)

    assert context.user_data["gen_razon_social"] == "Clinica Sonrisa SAS"
    assert result == GEN_NIT


async def test_ciudad_con_contrato_av_pide_plan() -> None:
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "Medellin"
    context = MagicMock()
    context.user_data = {"gen_docs": {_CAV}}

    result = await handle_ciudad(update, context)

    assert result == GEN_PLAN_CONTRATO


async def test_ciudad_solo_contrato_software_genera() -> None:
    svc = MagicMock()
    svc.generar.return_value = "<c/>"
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.text = "Medellin"
    context = MagicMock()
    context.user_data = {"gen_docs": {_CSW}, "gen_empresa": "Acme", **_LEGAL}
    context.bot_data = {"contrato_software_service": svc}

    result = await handle_ciudad(update, context)

    svc.generar.assert_called_once()
    ctx = svc.generar.call_args[0][0]
    assert ctx.datos_cliente is not None
    assert ctx.datos_cliente.nit == "900123456-7"
    update.effective_message.reply_document.assert_called_once()
    assert result == ConversationHandler.END


async def test_plan_contrato_genera_contrato_audiovisual_con_plan() -> None:
    from garay.dominio.propuestas.contexto import PlanAudiovisual

    svc = MagicMock()
    svc.generar.return_value = "<c/>"
    query = AsyncMock()
    query.data = "gen_plan:medio"
    update = MagicMock()
    update.callback_query = query
    update.effective_message = AsyncMock()
    context = MagicMock()
    context.user_data = {"gen_docs": {_CAV}, "gen_empresa": "Acme", **_LEGAL}
    context.bot_data = {"contrato_audiovisual_service": svc}

    result = await handle_plan_contrato(update, context)

    svc.generar.assert_called_once()
    ctx = svc.generar.call_args[0][0]
    assert ctx.plan_audiovisual is PlanAudiovisual.MEDIO
    assert ctx.datos_cliente.razon_social == "Clinica Sonrisa SAS"
    assert result == ConversationHandler.END
