"""Tests for /nuevo_egreso ConversationHandler — RED phase."""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.handlers_egresos import (
    EGRESO_CATEGORIA,
    EGRESO_CONFIRMACION,
    EGRESO_DESCRIPCION,
    EGRESO_FECHA,
    EGRESO_MONTO,
    cmd_nuevo_egreso,
    handle_egreso_categoria,
    handle_egreso_confirmacion,
    handle_egreso_descripcion,
    handle_egreso_fecha,
    handle_egreso_monto,
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


def _make_admin_repo() -> MagicMock:
    """Freelancer repo whose lookup returns an admin — satisfies requiere_admin_conv."""
    repo = MagicMock()
    freelancer = MagicMock()
    freelancer.es_admin = True
    repo.buscar_por_telegram_id.return_value = freelancer
    return repo


def _make_context(categorias: list[str] | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    service = MagicMock()
    service.listar_categorias.return_value = categorias or ["arriendo", "nomina", "otro"]
    ctx.bot_data = {"egreso_service": service, "freelancer_repo": _make_admin_repo()}
    return ctx


class TestCmdNuevoEgreso:
    @pytest.mark.asyncio
    async def test_inicia_y_pide_monto(self) -> None:
        update = _make_update()
        ctx = _make_context()
        result = await cmd_nuevo_egreso(update, ctx)
        assert result == EGRESO_MONTO
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_admin_es_denegado(self) -> None:
        """Non-admin user → requiere_admin_conv ends the conversation, no monto prompt."""
        update = _make_update()
        ctx = _make_context()
        repo = ctx.bot_data["freelancer_repo"]
        repo.buscar_por_telegram_id.return_value.es_admin = False
        result = await cmd_nuevo_egreso(update, ctx)
        assert result == ConversationHandler.END


class TestHandleEgresoMonto:
    @pytest.mark.asyncio
    async def test_monto_valido_avanza(self) -> None:
        update = _make_update(text="50")  # 50 → 50000
        ctx = _make_context()
        result = await handle_egreso_monto(update, ctx)
        assert result == EGRESO_DESCRIPCION
        assert ctx.user_data["egreso_monto"] == Decimal("50000")

    @pytest.mark.asyncio
    async def test_monto_invalido_repite_estado(self) -> None:
        update = _make_update(text="abc")
        ctx = _make_context()
        result = await handle_egreso_monto(update, ctx)
        assert result == EGRESO_MONTO

    @pytest.mark.asyncio
    async def test_monto_escrito_completo(self) -> None:
        update = _make_update(text="500000")
        ctx = _make_context()
        result = await handle_egreso_monto(update, ctx)
        assert result == EGRESO_DESCRIPCION
        assert ctx.user_data["egreso_monto"] == Decimal("500000")

    @pytest.mark.asyncio
    async def test_monto_con_puntos(self) -> None:
        update = _make_update(text="500.000")
        ctx = _make_context()
        result = await handle_egreso_monto(update, ctx)
        assert result == EGRESO_DESCRIPCION
        assert ctx.user_data["egreso_monto"] == Decimal("500000")


class TestHandleEgresoDescripcion:
    @pytest.mark.asyncio
    async def test_guarda_descripcion_y_avanza(self) -> None:
        update = _make_update(text="Pago arriendo")
        ctx = _make_context()
        result = await handle_egreso_descripcion(update, ctx)
        assert result == EGRESO_CATEGORIA
        assert ctx.user_data["egreso_descripcion"] == "Pago arriendo"

    @pytest.mark.asyncio
    async def test_muestra_botones_de_categorias(self) -> None:
        update = _make_update(text="Gasto")
        ctx = _make_context(categorias=["arriendo", "otro"])
        await handle_egreso_descripcion(update, ctx)
        update.effective_message.reply_text.assert_called_once()


class TestHandleEgresoCategoria:
    @pytest.mark.asyncio
    async def test_categoria_valida_avanza(self) -> None:
        update = _make_update(callback_data="arriendo")
        ctx = _make_context()
        result = await handle_egreso_categoria(update, ctx)
        assert result == EGRESO_FECHA
        assert ctx.user_data["egreso_categoria"] == "arriendo"

    @pytest.mark.asyncio
    async def test_categoria_invalida_repite(self) -> None:
        update = _make_update(callback_data="inexistente")
        ctx = _make_context(categorias=["arriendo"])
        result = await handle_egreso_categoria(update, ctx)
        assert result == EGRESO_CATEGORIA


class TestHandleEgresoFecha:
    @pytest.mark.asyncio
    async def test_fecha_hoy(self) -> None:
        update = _make_update(text="hoy")
        ctx = _make_context()
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_CONFIRMACION
        assert ctx.user_data["egreso_fecha"] == datetime.date.today()

    @pytest.mark.asyncio
    async def test_fecha_ddmm(self) -> None:
        update = _make_update(text="01/07")
        ctx = _make_context()
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_CONFIRMACION
        stored = ctx.user_data["egreso_fecha"]
        assert stored.day == 1
        assert stored.month == 7

    @pytest.mark.asyncio
    async def test_fecha_completa(self) -> None:
        update = _make_update(text="15/06/2026")
        ctx = _make_context()
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_CONFIRMACION
        assert ctx.user_data["egreso_fecha"] == datetime.date(2026, 6, 15)

    @pytest.mark.asyncio
    async def test_fecha_invalida_repite(self) -> None:
        update = _make_update(text="noesuna fecha")
        ctx = _make_context()
        result = await handle_egreso_fecha(update, ctx)
        assert result == EGRESO_FECHA


class TestHandleEgresoConfirmacion:
    @pytest.mark.asyncio
    async def test_confirmar_llama_service_y_termina(self) -> None:
        update = _make_update(callback_data="confirmar")
        ctx = _make_context()
        ctx.user_data.update(
            {
                "egreso_monto": Decimal("500000"),
                "egreso_descripcion": "Arriendo",
                "egreso_categoria": "arriendo",
                "egreso_fecha": datetime.date(2026, 7, 1),
            }
        )
        result = await handle_egreso_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["egreso_service"]
        service.registrar.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancelar_termina_sin_registrar(self) -> None:
        update = _make_update(callback_data="cancelar")
        ctx = _make_context()
        result = await handle_egreso_confirmacion(update, ctx)
        assert result == ConversationHandler.END
        service = ctx.bot_data["egreso_service"]
        service.registrar.assert_not_called()
