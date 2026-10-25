"""Tests for editar-referido handler task 3.5."""

from __future__ import annotations
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram.ext import ConversationHandler
from garay.dominio.comun.dinero import Dinero
from garay.dominio.ventas.errores import MismoReferido
from garay.infraestructura.telegram.handlers_gestion_ventas import (
    GV_EDIT_REFERIDO,
    GV_MOTIVO,
    _construir_teclado_campos,
    handle_gv_capturar_referido,
    handle_gv_referido_sin,
)


def _make_venta(referido_alias: str | None = None) -> MagicMock:
    from garay.dominio.comun.tipos import TipoCliente
    v = MagicMock()
    v.id = uuid.uuid4()
    v.servicio_ids = [uuid.uuid4()]
    v.valor_venta = Dinero(Decimal("500000"), "COP")
    v.neto = Dinero(Decimal("400000"), "COP")
    v.participantes = MagicMock()
    v.participantes.vendedor_nombre = "Ana"
    v.participantes.cerrador_nombre = None
    v.participantes.referido_alias = referido_alias
    v.tipo_cliente = TipoCliente.EXTERNO
    v.abono = None
    return v


def _make_context(referido_service: MagicMock | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = AsyncMock()
    ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    ctx.bot.delete_message = AsyncMock()
    venta_repo = MagicMock()
    venta_repo.buscar_por_id.return_value = _make_venta()
    venta_repo.actualizar_mensaje_grupo_id = MagicMock()
    freelancer_repo = MagicMock()
    fl = MagicMock()
    fl.nombre = "Admin"
    freelancer_repo.buscar_por_telegram_id.return_value = fl
    socios_config_repo = MagicMock()
    socios_config_repo.listar.return_value = []
    ctx.bot_data = {
        "venta_repo": venta_repo,
        "freelancer_repo": freelancer_repo,
        "socios_config_repo": socios_config_repo,
        "grupo_id": "-1001234567",
        "editar_referido_venta_service": referido_service or MagicMock(),
    }
    return ctx


def _make_update(text: str | None = None, callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 5870211102
    update.effective_message = AsyncMock()
    if text is not None:
        update.callback_query = None
        update.message = MagicMock()
        update.message.text = text
    elif callback_data is not None:
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
        update.callback_query.answer = AsyncMock()
        update.message = None
    else:
        update.callback_query = None
        update.message = None
    return update


class TestConstruirTecladoCamposReferido:
    def test_admin_ve_boton_referido(self) -> None:
        venta = _make_venta()
        teclado = _construir_teclado_campos(venta, es_admin=True)
        buttons = [btn.callback_data for row in teclado.inline_keyboard for btn in row]
        assert "gv_campo:referido" in buttons

    def test_no_admin_no_ve_boton_referido(self) -> None:
        venta = _make_venta()
        teclado = _construir_teclado_campos(venta, es_admin=False)
        buttons = [btn.callback_data for row in teclado.inline_keyboard for btn in row]
        assert "gv_campo:referido" not in buttons


class TestGvCampoReferidoPrompt:
    @pytest.mark.asyncio
    async def test_case_b_muestra_boton_sin_referido(self) -> None:
        venta = _make_venta(referido_alias="taxi")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta
        ctx.user_data["gv_venta_id"] = str(venta.id)
        update = _make_update(callback_data="gv_campo:referido")
        query = update.callback_query
        query.from_user = MagicMock()
        query.from_user.id = 5870211102
        query.data = "gv_campo:referido"
        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.es_admin_o_propietario",
            return_value=True,
        ):
            from garay.infraestructura.telegram.handlers_gestion_ventas import handle_gv_edit_campo
            result = await handle_gv_edit_campo(update, ctx)
        assert result == GV_EDIT_REFERIDO
        query.edit_message_text.assert_called_once()
        call_kwargs = query.edit_message_text.call_args[1]
        markup = call_kwargs.get("reply_markup")
        assert markup is not None
        buttons = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "gv_referido_sin" in buttons

    @pytest.mark.asyncio
    async def test_case_a_no_tiene_boton_sin_referido(self) -> None:
        venta = _make_venta(referido_alias=None)
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta
        ctx.user_data["gv_venta_id"] = str(venta.id)
        update = _make_update(callback_data="gv_campo:referido")
        query = update.callback_query
        query.from_user = MagicMock()
        query.from_user.id = 5870211102
        query.data = "gv_campo:referido"
        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.es_admin_o_propietario",
            return_value=True,
        ):
            from garay.infraestructura.telegram.handlers_gestion_ventas import handle_gv_edit_campo
            result = await handle_gv_edit_campo(update, ctx)
        assert result == GV_EDIT_REFERIDO
        call_kwargs = query.edit_message_text.call_args[1]
        markup = call_kwargs.get("reply_markup")
        assert markup is None


class TestCapturarReferido:
    @pytest.mark.asyncio
    async def test_alias_vacio_reprompts(self) -> None:
        update = _make_update(text="   ")
        ctx = _make_context()
        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.cerrar_flujo",
            new_callable=AsyncMock,
        ):
            result = await handle_gv_capturar_referido(update, ctx)
        assert result == GV_EDIT_REFERIDO
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_alias_valido_guarda_y_pide_motivo(self) -> None:
        update = _make_update(text="  mototaxi  ")
        ctx = _make_context()
        result = await handle_gv_capturar_referido(update, ctx)
        assert result == GV_MOTIVO
        assert ctx.user_data["gv_nuevo_referido"] == "mototaxi"


class TestGvReferidoSin:
    @pytest.mark.asyncio
    async def test_sets_nuevo_referido_none_y_pide_motivo(self) -> None:
        update = _make_update(callback_data="gv_referido_sin")
        ctx = _make_context()
        ctx.user_data["gv_referido_anterior"] = "taxi"
        result = await handle_gv_referido_sin(update, ctx)
        assert result == GV_MOTIVO
        assert "gv_nuevo_referido" in ctx.user_data
        assert ctx.user_data["gv_nuevo_referido"] is None


class TestConfirmarEditarReferido:
    @pytest.mark.asyncio
    async def test_service_called_con_comando_correcto(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarReferidoVentaComando
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _handle_confirmar_editar_referido,
        )
        service = MagicMock()
        service.ejecutar = MagicMock()
        venta_id = uuid.uuid4()
        ctx = _make_context(referido_service=service)
        ctx.user_data = {
            "gv_venta_id": str(venta_id),
            "gv_motivo": "solicitud cliente",
            "gv_nuevo_referido": "moto",
            "gv_referido_anterior": "taxi",
        }
        update = MagicMock()
        update.effective_message = AsyncMock()
        user = MagicMock()
        user.id = 5870211102
        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.cerrar_flujo",
            new_callable=AsyncMock,
            return_value=ConversationHandler.END,
        ):
            await _handle_confirmar_editar_referido(update, ctx, ctx.user_data, user)
        service.ejecutar.assert_called_once()
        cmd: EditarReferidoVentaComando = service.ejecutar.call_args[0][0]
        assert cmd.venta_id == venta_id
        assert cmd.nuevo_referido_alias == "moto"
        assert cmd.motivo == "solicitud cliente"
        assert cmd.realizada_por_telegram_id == 5870211102

    @pytest.mark.asyncio
    async def test_mismo_referido_muestra_error_sin_excepcion(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import (
            _handle_confirmar_editar_referido,
        )
        service = MagicMock()
        service.ejecutar = MagicMock(side_effect=MismoReferido("igual"))
        venta_id = uuid.uuid4()
        ctx = _make_context(referido_service=service)
        ctx.user_data = {
            "gv_venta_id": str(venta_id),
            "gv_motivo": "test",
            "gv_nuevo_referido": "taxi",
            "gv_referido_anterior": "taxi",
        }
        update = MagicMock()
        update.effective_message = AsyncMock()
        user = MagicMock()
        user.id = 5870211102
        with patch(
            "garay.infraestructura.telegram.handlers_gestion_ventas.cerrar_flujo",
            new_callable=AsyncMock,
            return_value=ConversationHandler.END,
        ):
            await _handle_confirmar_editar_referido(update, ctx, ctx.user_data, user)
        update.effective_message.reply_text.assert_called_once()


class TestGvEditReferidoWiring:
    def test_gv_edit_referido_state_registered(self) -> None:
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_REFERIDO
        with patch("garay.infraestructura.telegram.bot.obtener_settings") as mock_settings:
            settings = MagicMock()
            settings.propietario_telegram_ids = ""
            settings.dev_telegram_ids = ""
            mock_settings.return_value = settings
            from garay.infraestructura.telegram.bot import crear_aplicacion
            app = crear_aplicacion("fake:token")
        for handler_group in app.handlers.values():
            for handler in handler_group:
                if isinstance(handler, ConversationHandler) and GV_EDIT_REFERIDO in handler.states:
                    return
        pytest.fail("GV_EDIT_REFERIDO not registered")
