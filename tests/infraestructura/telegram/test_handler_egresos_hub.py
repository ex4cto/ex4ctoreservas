"""Tests for the /egresos hub menu (routes to nuevo egreso, gastos fijos, categorías)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.infraestructura.telegram.handlers_egresos import (
    CB_HUB_CANCELAR,
    CB_HUB_CATEGORIAS,
    CB_HUB_FIJOS,
    CB_HUB_NUEVO,
    cmd_egresos,
    handle_hub_cancelar,
)


def _make_update(callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_message = AsyncMock()
    if callback_data is not None:
        update.message = None
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
    else:
        update.message = None
        update.callback_query = None
    return update


def _make_admin_repo(es_admin: bool = True) -> MagicMock:
    repo = MagicMock()
    freelancer = MagicMock()
    freelancer.es_admin = es_admin
    repo.buscar_por_telegram_id.return_value = freelancer
    return repo


def _make_context(es_admin: bool = True) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot_data = {"freelancer_repo": _make_admin_repo(es_admin)}
    return ctx


def _labels_datas(update: MagicMock) -> list[str]:
    markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


class TestHubMenu:
    @pytest.mark.asyncio
    async def test_muestra_las_cuatro_opciones(self) -> None:
        update = _make_update()
        ctx = _make_context()
        await cmd_egresos(update, ctx)
        datas = _labels_datas(update)
        assert CB_HUB_NUEVO in datas
        assert CB_HUB_FIJOS in datas
        assert CB_HUB_CATEGORIAS in datas
        assert CB_HUB_CANCELAR in datas

    @pytest.mark.asyncio
    async def test_no_admin_no_ve_menu(self) -> None:
        update = _make_update()
        ctx = _make_context(es_admin=False)
        await cmd_egresos(update, ctx)
        # requiere_admin envía un mensaje de denegación SIN los botones del hub.
        markup = update.effective_message.reply_text.call_args.kwargs.get("reply_markup")
        assert markup is None


class TestHubCancelar:
    @pytest.mark.asyncio
    async def test_cancelar_cierra_sin_botones(self) -> None:
        update = _make_update(callback_data=CB_HUB_CANCELAR)
        ctx = _make_context()
        await handle_hub_cancelar(update, ctx)
        update.callback_query.edit_message_text.assert_called_once()
        # El cierre no debe llevar teclado (no botones colgados).
        assert update.callback_query.edit_message_text.call_args.kwargs.get("reply_markup") is None
