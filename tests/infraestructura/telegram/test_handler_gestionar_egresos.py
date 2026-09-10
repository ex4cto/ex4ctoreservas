"""Tests for /gestionar_egresos UI (list manual egresos → select → edit field)."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.infraestructura.telegram.handlers_egresos import (
    CB_GE_CERRAR,
    CB_GE_MONTO,
    CB_HOY,
    CB_OMITIR,
    GE_DETALLE,
    GE_EDIT_VALOR,
    GE_SELECCIONAR,
    PREFIJO_GE_SEL,
    _hoy_bogota,
    cmd_gestionar_egresos,
    handle_ge_detalle,
    handle_ge_edit_valor,
    handle_ge_seleccionar,
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


def _egreso() -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Concepto",
        monto=Dinero("50000", "COP"),
        fecha=datetime.date(2026, 7, 1),
        categoria="otro",
        tipo=TipoEgreso.MANUAL,
        destinatario="Proveedor A",
    )


def _make_context(
    egresos: list[Egreso] | None = None,
    egreso: Egreso | None = None,
    categorias: list[str] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    editar = MagicMock()
    editar.listar_editables.return_value = egresos if egresos is not None else []
    egreso_service = MagicMock()
    egreso_service.listar_categorias.return_value = categorias or ["transporte", "otro"]
    egreso_repo = MagicMock()
    egreso_repo.buscar_por_id.return_value = egreso
    freelancer_repo = MagicMock()
    fl = MagicMock()
    fl.es_admin = True
    fl.nombre = "Garay"
    freelancer_repo.buscar_por_telegram_id.return_value = fl
    ctx.bot_data = {
        "editar_egreso_service": editar,
        "egreso_service": egreso_service,
        "egreso_repo": egreso_repo,
        "freelancer_repo": freelancer_repo,
    }
    return ctx


class TestCmd:
    @pytest.mark.asyncio
    async def test_lista_manuales(self) -> None:
        e = _egreso()
        ctx = _make_context(egresos=[e])
        update = _make_update()
        result = await cmd_gestionar_egresos(update, ctx)
        assert result == GE_SELECCIONAR
        markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        datas = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert f"{PREFIJO_GE_SEL}0" in datas

    @pytest.mark.asyncio
    async def test_vacio_termina(self) -> None:
        ctx = _make_context(egresos=[])
        update = _make_update()
        result = await cmd_gestionar_egresos(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_no_admin_denegado(self) -> None:
        ctx = _make_context(egresos=[_egreso()])
        ctx.bot_data["freelancer_repo"].buscar_por_telegram_id.return_value.es_admin = False
        update = _make_update()
        result = await cmd_gestionar_egresos(update, ctx)
        assert result == ConversationHandler.END


class TestSeleccionar:
    @pytest.mark.asyncio
    async def test_seleccionar_abre_detalle(self) -> None:
        e = _egreso()
        ctx = _make_context(egresos=[e], egreso=e)
        await cmd_gestionar_egresos(_make_update(), ctx)
        update = _make_update(callback_data=f"{PREFIJO_GE_SEL}0")
        result = await handle_ge_seleccionar(update, ctx)
        assert result == GE_DETALLE
        assert ctx.user_data["ge_egreso_id"] == str(e.id)

    @pytest.mark.asyncio
    async def test_cerrar_termina(self) -> None:
        ctx = _make_context()
        update = _make_update(callback_data=CB_GE_CERRAR)
        result = await handle_ge_seleccionar(update, ctx)
        assert result == ConversationHandler.END


class TestDetalle:
    @pytest.mark.asyncio
    async def test_monto_pide_valor(self) -> None:
        e = _egreso()
        ctx = _make_context(egreso=e)
        ctx.user_data["ge_egreso_id"] = str(e.id)
        update = _make_update(callback_data=CB_GE_MONTO)
        result = await handle_ge_detalle(update, ctx)
        assert result == GE_EDIT_VALOR
        assert ctx.user_data["ge_campo"] == "monto"

    @pytest.mark.asyncio
    async def test_cerrar_termina(self) -> None:
        ctx = _make_context()
        update = _make_update(callback_data=CB_GE_CERRAR)
        result = await handle_ge_detalle(update, ctx)
        assert result == ConversationHandler.END


class TestEditValor:
    @pytest.mark.asyncio
    async def test_monto_valido_aplica_y_vuelve(self) -> None:
        e = _egreso()
        ctx = _make_context(egreso=e)
        ctx.user_data.update({"ge_campo": "monto", "ge_egreso_id": str(e.id)})
        update = _make_update(text="75")  # 75 → 75000
        result = await handle_ge_edit_valor(update, ctx)
        assert result == GE_DETALLE
        editar = ctx.bot_data["editar_egreso_service"]
        editar.editar_monto.assert_called_once()
        assert editar.editar_monto.call_args.args[1] == Decimal("75000")

    @pytest.mark.asyncio
    async def test_monto_invalido_repite(self) -> None:
        e = _egreso()
        ctx = _make_context(egreso=e)
        ctx.user_data.update({"ge_campo": "monto", "ge_egreso_id": str(e.id)})
        update = _make_update(text="abc")
        result = await handle_ge_edit_valor(update, ctx)
        assert result == GE_EDIT_VALOR
        ctx.bot_data["editar_egreso_service"].editar_monto.assert_not_called()

    @pytest.mark.asyncio
    async def test_categoria_valida_aplica(self) -> None:
        e = _egreso()
        ctx = _make_context(egreso=e, categorias=["transporte", "otro"])
        ctx.user_data.update({"ge_campo": "categoria", "ge_egreso_id": str(e.id)})
        update = _make_update(callback_data="transporte")
        result = await handle_ge_edit_valor(update, ctx)
        assert result == GE_DETALLE
        ctx.bot_data["editar_egreso_service"].editar_categoria.assert_called_once()

    @pytest.mark.asyncio
    async def test_categoria_invalida_repite(self) -> None:
        e = _egreso()
        ctx = _make_context(egreso=e, categorias=["transporte", "otro"])
        ctx.user_data.update({"ge_campo": "categoria", "ge_egreso_id": str(e.id)})
        update = _make_update(callback_data="inexistente")
        result = await handle_ge_edit_valor(update, ctx)
        assert result == GE_EDIT_VALOR
        ctx.bot_data["editar_egreso_service"].editar_categoria.assert_not_called()

    @pytest.mark.asyncio
    async def test_fecha_hoy_aplica(self) -> None:
        e = _egreso()
        ctx = _make_context(egreso=e)
        ctx.user_data.update({"ge_campo": "fecha", "ge_egreso_id": str(e.id)})
        update = _make_update(callback_data=CB_HOY)
        result = await handle_ge_edit_valor(update, ctx)
        assert result == GE_DETALLE
        editar = ctx.bot_data["editar_egreso_service"]
        editar.editar_fecha.assert_called_once()
        assert editar.editar_fecha.call_args.args[1] == _hoy_bogota()

    @pytest.mark.asyncio
    async def test_destinatario_omitir_aplica_none(self) -> None:
        e = _egreso()
        ctx = _make_context(egreso=e)
        ctx.user_data.update({"ge_campo": "destinatario", "ge_egreso_id": str(e.id)})
        update = _make_update(callback_data=CB_OMITIR)
        result = await handle_ge_edit_valor(update, ctx)
        assert result == GE_DETALLE
        editar = ctx.bot_data["editar_egreso_service"]
        editar.editar_destinatario.assert_called_once()
        assert editar.editar_destinatario.call_args.args[1] is None
