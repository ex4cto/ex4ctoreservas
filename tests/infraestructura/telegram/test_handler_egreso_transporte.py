"""Tests for B2: transporte preventive notice + duplicate guard on nuevo egreso."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.handlers_egresos import (
    CB_CANCELAR,
    CB_DUP_OTRO,
    EGRESO_CONFIRMACION,
    EGRESO_DESTINATARIO,
    EGRESO_DUP_CONFIRM,
    handle_egreso_categoria,
    handle_egreso_dup_confirm,
    handle_egreso_fecha,
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


def _make_context(
    categorias: list[str] | None = None, egreso_repo: object | None = None
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    service = MagicMock()
    service.listar_categorias.return_value = categorias or ["transporte", "otro"]
    ctx.bot_data = {"egreso_service": service, "egreso_repo": egreso_repo}
    return ctx


def _egreso_mock(monto: Decimal) -> MagicMock:
    e = MagicMock()
    e.monto.monto = monto
    return e


def _texto_enviado(update: MagicMock) -> str:
    if update.callback_query is not None:
        return str(update.callback_query.edit_message_text.call_args[0][0])
    return str(update.effective_message.reply_text.call_args[0][0])


class TestTransporteAviso:
    @pytest.mark.asyncio
    async def test_categoria_transporte_muestra_aviso(self) -> None:
        ctx = _make_context(categorias=["transporte", "otro"])
        update = _make_update(callback_data="transporte")
        result = await handle_egreso_categoria(update, ctx)
        assert result == EGRESO_DESTINATARIO
        msg = _texto_enviado(update)
        assert "inDriver" in msg

    @pytest.mark.asyncio
    async def test_categoria_no_transporte_sin_aviso(self) -> None:
        ctx = _make_context(categorias=["transporte", "otro"])
        update = _make_update(callback_data="otro")
        result = await handle_egreso_categoria(update, ctx)
        assert result == EGRESO_DESTINATARIO
        assert "inDriver" not in _texto_enviado(update)


class TestGuardiaDuplicado:
    @pytest.mark.asyncio
    async def test_transporte_con_duplicado_pide_confirmacion(self) -> None:
        egreso_repo = MagicMock()
        egreso_repo.listar_por_periodo.return_value = [_egreso_mock(Decimal("50000"))]
        ctx = _make_context(egreso_repo=egreso_repo)
        ctx.user_data.update(
            {
                "egreso_categoria": "transporte",
                "egreso_monto": Decimal("50000"),
                "egreso_descripcion": "InDriver",
            }
        )
        update = _make_update(text="01/07/2026")
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_DUP_CONFIRM

    @pytest.mark.asyncio
    async def test_transporte_sin_duplicado_va_a_confirmacion(self) -> None:
        egreso_repo = MagicMock()
        egreso_repo.listar_por_periodo.return_value = [_egreso_mock(Decimal("99999"))]
        ctx = _make_context(egreso_repo=egreso_repo)
        ctx.user_data.update(
            {"egreso_categoria": "transporte", "egreso_monto": Decimal("50000")}
        )
        update = _make_update(text="01/07/2026")
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_CONFIRMACION

    @pytest.mark.asyncio
    async def test_no_transporte_no_chequea_duplicado(self) -> None:
        egreso_repo = MagicMock()
        egreso_repo.listar_por_periodo.return_value = [_egreso_mock(Decimal("50000"))]
        ctx = _make_context(egreso_repo=egreso_repo)
        ctx.user_data.update(
            {"egreso_categoria": "otro", "egreso_monto": Decimal("50000")}
        )
        update = _make_update(text="01/07/2026")
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_CONFIRMACION
        egreso_repo.listar_por_periodo.assert_not_called()

    @pytest.mark.asyncio
    async def test_editar_fecha_no_dispara_guardia(self) -> None:
        egreso_repo = MagicMock()
        egreso_repo.listar_por_periodo.return_value = [_egreso_mock(Decimal("50000"))]
        ctx = _make_context(egreso_repo=egreso_repo)
        ctx.user_data.update(
            {
                "egreso_categoria": "transporte",
                "egreso_monto": Decimal("50000"),
                "editando": True,
            }
        )
        update = _make_update(text="01/07/2026")
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_CONFIRMACION


class TestDupConfirm:
    @pytest.mark.asyncio
    async def test_es_otro_va_a_confirmacion(self) -> None:
        ctx = _make_context()
        ctx.user_data.update(
            {
                "egreso_categoria": "transporte",
                "egreso_monto": Decimal("50000"),
                "egreso_descripcion": "InDriver",
            }
        )
        update = _make_update(callback_data=CB_DUP_OTRO)
        result = await handle_egreso_dup_confirm(update, ctx)
        assert result == EGRESO_CONFIRMACION

    @pytest.mark.asyncio
    async def test_cancelar_termina(self) -> None:
        ctx = _make_context()
        update = _make_update(callback_data=CB_CANCELAR)
        result = await handle_egreso_dup_confirm(update, ctx)
        assert result == ConversationHandler.END
