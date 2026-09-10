"""Tests for D: notify the dev when a manual egreso / gasto fijo payment is registered."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

import garay.infraestructura.telegram.handlers_egresos as he
from garay.infraestructura.telegram.handlers_egresos import (
    handle_egreso_confirmacion,
    handle_egreso_rec_confirmacion,
)


def _make_update() -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_message = AsyncMock()
    update.message = None
    update.callback_query = AsyncMock()
    update.callback_query.data = "confirmar"
    return update


def _make_context() -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = AsyncMock()
    egreso_service = MagicMock()
    freelancer_repo = MagicMock()
    fl = MagicMock()
    fl.es_admin = True
    fl.nombre = "Sharimel"
    freelancer_repo.buscar_por_telegram_id.return_value = fl
    ctx.bot_data = {"egreso_service": egreso_service, "freelancer_repo": freelancer_repo}
    return ctx


class TestAvisoDevEgresoManual:
    @pytest.mark.asyncio
    async def test_avisa_al_dev_al_confirmar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(he, "dev_telegram_ids", lambda: {999})
        ctx = _make_context()
        ctx.user_data.update(
            {
                "egreso_monto": Decimal("50000"),
                "egreso_descripcion": "Lancha",
                "egreso_categoria": "proveedores tour",
                "egreso_fecha": datetime.date(2026, 7, 1),
            }
        )
        await handle_egreso_confirmacion(_make_update(), ctx)
        ctx.bot.send_message.assert_called_once()
        assert ctx.bot.send_message.call_args.kwargs["chat_id"] == 999
        texto = ctx.bot.send_message.call_args.kwargs["text"]
        assert "Sharimel" in texto
        assert "Lancha" in texto

    @pytest.mark.asyncio
    async def test_sin_devs_no_avisa(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(he, "dev_telegram_ids", lambda: set())
        ctx = _make_context()
        ctx.user_data.update(
            {
                "egreso_monto": Decimal("50000"),
                "egreso_descripcion": "X",
                "egreso_categoria": "otro",
                "egreso_fecha": datetime.date(2026, 7, 1),
            }
        )
        await handle_egreso_confirmacion(_make_update(), ctx)
        ctx.bot.send_message.assert_not_called()


class TestAvisoDevGastoFijo:
    @pytest.mark.asyncio
    async def test_avisa_al_pagar_gasto_fijo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(he, "dev_telegram_ids", lambda: {999})
        ctx = _make_context()
        ctx.user_data.update(
            {
                "rec_id": uuid.uuid4(),
                "rec_nombre": "Arriendo",
                "rec_categoria": "servicios fijos",
                "rec_monto": Decimal("800000"),
                "rec_fecha": datetime.date(2026, 7, 1),
            }
        )
        await handle_egreso_rec_confirmacion(_make_update(), ctx)
        ctx.bot.send_message.assert_called_once()
        assert ctx.bot.send_message.call_args.kwargs["chat_id"] == 999
        assert "Arriendo" in ctx.bot.send_message.call_args.kwargs["text"]
