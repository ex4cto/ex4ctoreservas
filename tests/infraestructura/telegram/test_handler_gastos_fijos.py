"""Tests for /gastos_fijos handler."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import GastoRecurrente
from garay.infraestructura.telegram.handlers_egresos import (
    CB_GF_ATRAS,
    CB_GF_CERRAR,
    CB_GF_EDITAR_MONTO,
    CB_GF_LIQUIDAR,
    CB_GF_NUEVO,
    GF_CATEGORIA,
    GF_CONFIRMACION,
    GF_DETALLE,
    GF_DIA,
    GF_EDITAR_MONTO,
    GF_LISTA,
    GF_MONTO,
    GF_NOMBRE,
    PREFIJO_GF_SEL,
    cmd_gastos_fijos,
    cmd_nuevo_gasto_fijo,
    handle_gf_categoria,
    handle_gf_confirmacion,
    handle_gf_detalle,
    handle_gf_dia,
    handle_gf_editar_monto,
    handle_gf_lista,
    handle_gf_monto,
    handle_gf_nombre,
)


def _make_update(text: str | None = None, callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_message = AsyncMock()
    if text is not None:
        update.message = MagicMock()
        update.message.text = text
        update.callback_query = None
    elif callback_data is not None:
        update.message = None
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
    else:
        update.message = None
        update.callback_query = None
    return update


def _gasto_recurrente(nombre: str = "Arriendo", gasto_id: uuid.UUID | None = None) -> GastoRecurrente:
    return GastoRecurrente(
        id=gasto_id or uuid.uuid4(),
        nombre=nombre,
        monto=Dinero("500000"),
        categoria="arriendo",
        dia_mes=1,
        activo=True,
    )


def _make_admin_repo() -> MagicMock:
    repo = MagicMock()
    freelancer = MagicMock()
    freelancer.es_admin = True
    repo.buscar_por_telegram_id.return_value = freelancer
    return repo


def _make_context(
    gastos: list[GastoRecurrente] | None = None,
    categorias: list[str] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}

    recurrente_service = MagicMock()
    recurrente_service.listar_activos.return_value = gastos or []

    egreso_service = MagicMock()
    egreso_service.listar_categorias.return_value = categorias or ["arriendo", "nomina", "otro"]

    ctx.bot_data = {
        "egreso_service": egreso_service,
        "recurrente_service": recurrente_service,
        "freelancer_repo": _make_admin_repo(),
    }
    return ctx


class TestCmdGastosFijos:
    @pytest.mark.asyncio
    async def test_lista_gastos_activos_muestra_botones(self) -> None:
        g = _gasto_recurrente("Arriendo")
        ctx = _make_context(gastos=[g])
        update = _make_update()
        result = await cmd_gastos_fijos(update, ctx)
        assert result == GF_LISTA
        markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        labels = [btn.text for row in markup.inline_keyboard for btn in row]
        assert any("Arriendo" in lbl for lbl in labels)

    @pytest.mark.asyncio
    async def test_lista_vacia_muestra_botones_nuevo_y_cerrar(self) -> None:
        ctx = _make_context(gastos=[])
        update = _make_update()
        result = await cmd_gastos_fijos(update, ctx)
        assert result == GF_LISTA
        markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        datas = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert CB_GF_NUEVO in datas
        assert CB_GF_CERRAR in datas

    @pytest.mark.asyncio
    async def test_no_admin_es_denegado(self) -> None:
        ctx = _make_context(gastos=[_gasto_recurrente()])
        ctx.bot_data["freelancer_repo"].buscar_por_telegram_id.return_value.es_admin = False
        update = _make_update()
        result = await cmd_gastos_fijos(update, ctx)
        assert result == ConversationHandler.END
        ctx.bot_data["recurrente_service"].listar_activos.assert_not_called()


class TestLista:
    @pytest.mark.asyncio
    async def test_cerrar_termina(self) -> None:
        ctx = _make_context()
        update = _make_update(callback_data=CB_GF_CERRAR)
        result = await handle_gf_lista(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_nuevo_pide_nombre(self) -> None:
        ctx = _make_context()
        update = _make_update(callback_data=CB_GF_NUEVO)
        result = await handle_gf_lista(update, ctx)
        assert result == GF_NOMBRE

    @pytest.mark.asyncio
    async def test_seleccionar_gasto_abre_detalle(self) -> None:
        g = _gasto_recurrente("Arriendo")
        ctx = _make_context(gastos=[g])
        await cmd_gastos_fijos(_make_update(), ctx)
        ctx.bot_data["recurrente_service"].buscar_por_id.return_value = g
        update = _make_update(callback_data=f"{PREFIJO_GF_SEL}0")
        result = await handle_gf_lista(update, ctx)
        assert result == GF_DETALLE
        assert ctx.user_data["gf_sel_id"] == str(g.id)

    @pytest.mark.asyncio
    async def test_seleccionar_gasto_muestra_botones_detalle(self) -> None:
        g = _gasto_recurrente("Arriendo")
        ctx = _make_context(gastos=[g])
        await cmd_gastos_fijos(_make_update(), ctx)
        ctx.bot_data["recurrente_service"].buscar_por_id.return_value = g
        update = _make_update(callback_data=f"{PREFIJO_GF_SEL}0")
        await handle_gf_lista(update, ctx)
        markup = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
        datas = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert CB_GF_EDITAR_MONTO in datas
        assert CB_GF_LIQUIDAR in datas
        assert CB_GF_ATRAS in datas


class TestDetalle:
    def _ctx_with_gasto(self, g: GastoRecurrente) -> MagicMock:
        ctx = _make_context(gastos=[g])
        ctx.user_data["gf_sel_id"] = str(g.id)
        ctx.bot_data["recurrente_service"].buscar_por_id.return_value = g
        return ctx

    @pytest.mark.asyncio
    async def test_atras_vuelve_a_lista(self) -> None:
        g = _gasto_recurrente()
        ctx = self._ctx_with_gasto(g)
        update = _make_update(callback_data=CB_GF_ATRAS)
        result = await handle_gf_detalle(update, ctx)
        assert result == GF_LISTA

    @pytest.mark.asyncio
    async def test_editar_monto_pide_nuevo_valor(self) -> None:
        g = _gasto_recurrente()
        ctx = self._ctx_with_gasto(g)
        update = _make_update(callback_data=CB_GF_EDITAR_MONTO)
        result = await handle_gf_detalle(update, ctx)
        assert result == GF_EDITAR_MONTO

    @pytest.mark.asyncio
    async def test_liquidar_registra_egreso_y_vuelve_lista(self) -> None:
        g = _gasto_recurrente()
        ctx = self._ctx_with_gasto(g)
        update = _make_update(callback_data=CB_GF_LIQUIDAR)
        result = await handle_gf_detalle(update, ctx)
        assert result == GF_LISTA
        ctx.bot_data["egreso_service"].registrar.assert_called_once()
        call_kwargs = ctx.bot_data["egreso_service"].registrar.call_args
        assert call_kwargs.kwargs["gasto_recurrente_id"] == g.id


class TestEditarMonto:
    @pytest.mark.asyncio
    async def test_monto_valido_actualiza_y_vuelve_detalle(self) -> None:
        g = _gasto_recurrente()
        ctx = _make_context(gastos=[g])
        ctx.user_data["gf_sel_id"] = str(g.id)
        ctx.bot_data["recurrente_service"].buscar_por_id.return_value = g
        update = _make_update(text="300")
        result = await handle_gf_editar_monto(update, ctx)
        assert result == GF_DETALLE
        ctx.bot_data["recurrente_service"].guardar.assert_called_once()

    @pytest.mark.asyncio
    async def test_monto_invalido_repite(self) -> None:
        ctx = _make_context()
        update = _make_update(text="abc")
        result = await handle_gf_editar_monto(update, ctx)
        assert result == GF_EDITAR_MONTO
        ctx.bot_data["recurrente_service"].guardar.assert_not_called()


class TestCrearGastoFijo:
    @pytest.mark.asyncio
    async def test_cmd_nuevo_gasto_fijo_muestra_prompt(self) -> None:
        update = _make_update()
        ctx = _make_context()
        result = await cmd_nuevo_gasto_fijo(update, ctx)
        assert result == GF_NOMBRE
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_gf_nombre_avanza(self) -> None:
        update = _make_update(text="Arriendo oficina")
        ctx = _make_context()
        result = await handle_gf_nombre(update, ctx)
        assert result == GF_MONTO
        assert ctx.user_data["gf_nombre"] == "Arriendo oficina"

    @pytest.mark.asyncio
    async def test_handle_gf_monto_valido(self) -> None:
        update = _make_update(text="500")
        ctx = _make_context()
        result = await handle_gf_monto(update, ctx)
        assert result == GF_CATEGORIA
        assert ctx.user_data["gf_monto"] == Decimal("500000")

    @pytest.mark.asyncio
    async def test_handle_gf_monto_invalido_repite(self) -> None:
        update = _make_update(text="abc")
        ctx = _make_context()
        result = await handle_gf_monto(update, ctx)
        assert result == GF_MONTO

    @pytest.mark.asyncio
    async def test_handle_gf_categoria_valida(self) -> None:
        update = _make_update(callback_data="arriendo")
        ctx = _make_context()
        result = await handle_gf_categoria(update, ctx)
        assert result == GF_DIA
        assert ctx.user_data["gf_categoria"] == "arriendo"

    @pytest.mark.asyncio
    async def test_handle_gf_dia_valido(self) -> None:
        update = _make_update(text="15")
        ctx = _make_context()
        result = await handle_gf_dia(update, ctx)
        assert result == GF_CONFIRMACION
        assert ctx.user_data["gf_dia"] == 15

    @pytest.mark.asyncio
    async def test_handle_gf_dia_invalido_repite(self) -> None:
        update = _make_update(text="31")
        ctx = _make_context()
        result = await handle_gf_dia(update, ctx)
        assert result == GF_DIA

    @pytest.mark.asyncio
    async def test_handle_gf_dia_texto_invalido(self) -> None:
        update = _make_update(text="abc")
        ctx = _make_context()
        result = await handle_gf_dia(update, ctx)
        assert result == GF_DIA

    @pytest.mark.asyncio
    async def test_handle_gf_confirmacion_crear(self) -> None:
        update = _make_update(callback_data="confirmar")
        ctx = _make_context()
        ctx.user_data.update(
            {
                "gf_nombre": "Arriendo",
                "gf_monto": Decimal("500000"),
                "gf_categoria": "arriendo",
                "gf_dia": 1,
            }
        )
        result = await handle_gf_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["recurrente_service"]
        service.guardar.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_gf_confirmacion_cancelar(self) -> None:
        update = _make_update(callback_data="cancelar")
        ctx = _make_context()
        result = await handle_gf_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["recurrente_service"]
        service.guardar.assert_not_called()
