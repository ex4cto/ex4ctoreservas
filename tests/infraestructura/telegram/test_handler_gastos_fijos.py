"""Tests for /gastos_fijos and /generar_mes handlers — RED phase."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import GastoRecurrente
from garay.infraestructura.telegram.handlers_egresos import (
    GF_CATEGORIA,
    GF_CONFIRMACION,
    GF_DIA,
    GF_MONTO,
    cmd_gastos_fijos,
    cmd_generar_mes,
    handle_gf_categoria,
    handle_gf_confirmacion,
    handle_gf_dia,
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


def _gasto_recurrente(nombre: str = "Arriendo") -> GastoRecurrente:
    return GastoRecurrente(
        id=uuid.uuid4(),
        nombre=nombre,
        monto=Dinero("500000"),
        categoria="arriendo",
        dia_mes=1,
        activo=True,
    )


def _make_admin_repo() -> MagicMock:
    """Freelancer repo whose lookup returns an admin — satisfies requiere_admin(_conv)."""
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
    async def test_lista_gastos_activos(self) -> None:
        update = _make_update()
        ctx = _make_context(gastos=[_gasto_recurrente("Arriendo"), _gasto_recurrente("Nomina")])
        await cmd_gastos_fijos(update, ctx)
        update.effective_message.reply_text.assert_called_once()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "Arriendo" in msg

    @pytest.mark.asyncio
    async def test_mensaje_vacio_cuando_no_hay_gastos(self) -> None:
        update = _make_update()
        ctx = _make_context(gastos=[])
        await cmd_gastos_fijos(update, ctx)
        update.effective_message.reply_text.assert_called_once()
        msg = update.effective_message.reply_text.call_args[0][0]
        # Should show the "empty" message
        assert msg  # non-empty response

    @pytest.mark.asyncio
    async def test_no_admin_es_denegado(self) -> None:
        """Non-admin user → requiere_admin returns None, no gastos list shown."""
        update = _make_update()
        ctx = _make_context(gastos=[_gasto_recurrente("Arriendo")])
        ctx.bot_data["freelancer_repo"].buscar_por_telegram_id.return_value.es_admin = False
        result = await cmd_gastos_fijos(update, ctx)
        assert result is None
        ctx.bot_data["recurrente_service"].listar_activos.assert_not_called()


class TestCrearGastoFijo:
    @pytest.mark.asyncio
    async def test_handle_gf_nombre_avanza(self) -> None:
        update = _make_update(text="Arriendo oficina")
        ctx = _make_context()
        result = await handle_gf_nombre(update, ctx)
        assert result == GF_MONTO
        assert ctx.user_data["gf_nombre"] == "Arriendo oficina"

    @pytest.mark.asyncio
    async def test_handle_gf_nombre_no_admin_es_denegado(self) -> None:
        """Non-admin → requiere_admin_conv ends the create-flow at its real entry point."""
        update = _make_update(text="Arriendo oficina")
        ctx = _make_context()
        ctx.bot_data["freelancer_repo"].buscar_por_telegram_id.return_value.es_admin = False
        result = await handle_gf_nombre(update, ctx)
        assert result == ConversationHandler.END

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
        update = _make_update(text="31")  # > 28
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


class TestCmdGenerarMes:
    @pytest.mark.asyncio
    async def test_genera_egresos_del_mes(self) -> None:
        update = _make_update()
        ctx = _make_context()
        gen_service = MagicMock()
        gen_service.generar.return_value = [MagicMock(), MagicMock()]
        ctx.bot_data["generar_gastos_service"] = gen_service

        await cmd_generar_mes(update, ctx)

        gen_service.generar.assert_called_once()
        update.effective_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_sin_gastos_activos_responde(self) -> None:
        update = _make_update()
        ctx = _make_context(gastos=[])  # no active recurring expenses at all
        gen_service = MagicMock()
        gen_service.generar.return_value = []
        ctx.bot_data["generar_gastos_service"] = gen_service

        await cmd_generar_mes(update, ctx)

        update.effective_message.reply_text.assert_called_once()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "No hay gastos fijos activos" in msg

    @pytest.mark.asyncio
    async def test_ya_generados_cuando_hay_activos_pero_nada_nuevo(self) -> None:
        """Idempotent re-run: active expenses exist but all were already generated."""
        update = _make_update()
        ctx = _make_context(gastos=[_gasto_recurrente("Arriendo")])
        gen_service = MagicMock()
        gen_service.generar.return_value = []  # everything skipped by idempotency
        ctx.bot_data["generar_gastos_service"] = gen_service

        await cmd_generar_mes(update, ctx)

        msg = update.effective_message.reply_text.call_args[0][0]
        assert "ya fueron generados" in msg

    @pytest.mark.asyncio
    async def test_no_admin_es_denegado(self) -> None:
        """Non-admin user → requiere_admin returns None, generar service not called."""
        update = _make_update()
        ctx = _make_context()
        gen_service = MagicMock()
        gen_service.generar.return_value = [MagicMock()]
        ctx.bot_data["generar_gastos_service"] = gen_service
        ctx.bot_data["freelancer_repo"].buscar_por_telegram_id.return_value.es_admin = False

        result = await cmd_generar_mes(update, ctx)

        assert result is None
        gen_service.generar.assert_not_called()
