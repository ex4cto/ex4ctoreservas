"""Tests for /gestionar_ventas ConversationHandler — RED phase (TDD B2)."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.handlers_gestion_ventas import (
    GV_CONFIRMAR,
    GV_DETALLE,
    GV_MOTIVO,
    GV_SELECCIONAR,
    cmd_gestionar_ventas,
    handle_gv_confirmar,
    handle_gv_detalle,
    handle_gv_motivo,
    handle_gv_seleccionar,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_venta(
    venta_id: uuid.UUID | None = None,
    cliente_id: uuid.UUID | None = None,
    fecha: datetime.date | None = None,
    valor_monto: float = 500_000,
) -> MagicMock:
    v = MagicMock()
    v.id = venta_id or uuid.uuid4()
    v.cliente_id = cliente_id or uuid.uuid4()
    v.servicio_ids = [uuid.uuid4()]
    v.fecha = fecha or datetime.date(2026, 8, 1)
    v.valor_venta = MagicMock()
    v.valor_venta.monto = valor_monto
    return v


def _make_update(
    user_id: int = 123,
    callback_data: str | None = None,
    text: str | None = None,
) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    if callback_data is not None:
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
        update.message = None
    elif text is not None:
        update.callback_query = None
        update.message = MagicMock()
        update.message.text = text
    else:
        update.callback_query = None
        update.message = None
    return update


def _make_admin_freelancer() -> MagicMock:
    f = MagicMock()
    f.es_admin = True
    f.nombre = "Admin"
    return f


def _make_context(
    ventas: list[MagicMock] | None = None,
    freelancer: MagicMock | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}

    venta_repo = MagicMock()
    venta_repo.listar_por_periodo.return_value = ventas or []

    freelancer_repo = MagicMock()
    freelancer_repo.buscar_por_telegram_id.return_value = freelancer or _make_admin_freelancer()

    cliente_repo = MagicMock()
    cliente = MagicMock()
    cliente.nombre = "Juan Perez"
    cliente_repo.buscar_por_id.return_value = cliente

    servicio_repo = MagicMock()
    servicio = MagicMock()
    servicio.nombre = "Tour Isla"
    servicio_repo.buscar_por_id.return_value = servicio

    anular_service = MagicMock()

    ctx.bot_data = {
        "venta_repo": venta_repo,
        "freelancer_repo": freelancer_repo,
        "cliente_repo": cliente_repo,
        "servicio_repo": servicio_repo,
        "anular_venta_service": anular_service,
    }
    return ctx


# ---------------------------------------------------------------------------
# cmd_gestionar_ventas
# ---------------------------------------------------------------------------


class TestCmdGestionarVentas:
    @pytest.mark.asyncio
    async def test_sin_ventas_reply_y_end(self) -> None:
        update = _make_update()
        ctx = _make_context(ventas=[])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            result = await cmd_gestionar_ventas(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_con_ventas_muestra_botones_y_retorna_gv_seleccionar(self) -> None:
        ventas = [_make_venta(), _make_venta()]
        update = _make_update()
        ctx = _make_context(ventas=ventas)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            result = await cmd_gestionar_ventas(update, ctx)

        assert result == GV_SELECCIONAR
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_admin_no_propietario_devuelve_end(self) -> None:
        no_admin = MagicMock()
        no_admin.es_admin = False
        update = _make_update(user_id=999)
        ctx = _make_context(freelancer=no_admin)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            result = await cmd_gestionar_ventas(update, ctx)

        assert result == ConversationHandler.END
        # repo must NOT have been called because auth denied early
        ctx.bot_data["venta_repo"].listar_por_periodo.assert_not_called()


# ---------------------------------------------------------------------------
# handle_gv_seleccionar
# ---------------------------------------------------------------------------


class TestHandleGvSeleccionar:
    @pytest.mark.asyncio
    async def test_seleccionar_venta_valida_retorna_gv_detalle(self) -> None:
        venta = _make_venta()
        update = _make_update(callback_data=f"gv_sel:{venta.id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = venta

        result = await handle_gv_seleccionar(update, ctx)

        assert result == GV_DETALLE
        assert ctx.user_data["gv_venta_id"] == str(venta.id)

    @pytest.mark.asyncio
    async def test_seleccionar_venta_no_encontrada_retorna_end(self) -> None:
        venta_id = uuid.uuid4()
        update = _make_update(callback_data=f"gv_sel:{venta_id}")
        ctx = _make_context()
        ctx.bot_data["venta_repo"].buscar_por_id.return_value = None

        result = await handle_gv_seleccionar(update, ctx)

        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# handle_gv_detalle
# ---------------------------------------------------------------------------


class TestHandleGvDetalle:
    @pytest.mark.asyncio
    async def test_gv_anular_retorna_gv_motivo(self) -> None:
        update = _make_update(callback_data="gv_anular")
        ctx = _make_context()

        result = await handle_gv_detalle(update, ctx)

        assert result == GV_MOTIVO

    @pytest.mark.asyncio
    async def test_gv_cancelar_retorna_end(self) -> None:
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()

        result = await handle_gv_detalle(update, ctx)

        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# handle_gv_motivo
# ---------------------------------------------------------------------------


class TestHandleGvMotivo:
    @pytest.mark.asyncio
    async def test_motivo_vacio_stays_en_gv_motivo(self) -> None:
        update = _make_update(text="   ")
        ctx = _make_context()

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_MOTIVO

    @pytest.mark.asyncio
    async def test_motivo_vacio_reply_error(self) -> None:
        update = _make_update(text="")
        ctx = _make_context()

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_MOTIVO
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_motivo_valido_guarda_y_retorna_gv_confirmar(self) -> None:
        update = _make_update(text="Cliente cambio de planes")
        ctx = _make_context()

        result = await handle_gv_motivo(update, ctx)

        assert result == GV_CONFIRMAR
        assert ctx.user_data["gv_motivo"] == "Cliente cambio de planes"


# ---------------------------------------------------------------------------
# handle_gv_confirmar
# ---------------------------------------------------------------------------


class TestHandleGvConfirmar:
    @pytest.mark.asyncio
    async def test_cancelar_retorna_end(self) -> None:
        update = _make_update(callback_data="gv_cancelar")
        ctx = _make_context()

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_confirmar_llama_servicio_y_retorna_end(self) -> None:
        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar", user_id=123)
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo de prueba"

        from garay.aplicacion.ventas.comandos import AnularVentaComando

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        service = ctx.bot_data["anular_venta_service"]
        service.ejecutar.assert_called_once()
        cmd: AnularVentaComando = service.ejecutar.call_args[0][0]
        assert cmd.venta_id == venta_id
        assert cmd.motivo == "Motivo de prueba"
        assert cmd.realizada_por_telegram_id == 123

    @pytest.mark.asyncio
    async def test_confirmar_venta_ya_anulada_reply_error_y_end(self) -> None:
        from garay.dominio.ventas.errores import VentaYaAnulada

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.bot_data["anular_venta_service"].ejecutar.side_effect = VentaYaAnulada("ya anulada")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_confirmar_venta_no_encontrada_reply_error_y_end(self) -> None:
        from garay.dominio.ventas.errores import VentaNoEncontrada

        venta_id = uuid.uuid4()
        update = _make_update(callback_data="gv_confirmar")
        ctx = _make_context()
        ctx.user_data["gv_venta_id"] = str(venta_id)
        ctx.user_data["gv_motivo"] = "Motivo"
        ctx.bot_data["anular_venta_service"].ejecutar.side_effect = VentaNoEncontrada("no")

        result = await handle_gv_confirmar(update, ctx)

        assert result == ConversationHandler.END
        update.effective_message.reply_text.assert_called()
