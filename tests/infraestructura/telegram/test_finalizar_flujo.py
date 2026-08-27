"""Tests for finalizar_flujo — clean flow completion.

On any flow end it must: drop the leftover inline keyboard, send the final
message, then show the group's submenu with a /start hint, and return END.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import TelegramError
from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.handlers import cerrar_flujo, finalizar_flujo
from garay.infraestructura.telegram.menu import GrupoComando


def _make_update(*, con_callback: bool, uid: int = 888) -> MagicMock:
    update = MagicMock()
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    update.effective_message = msg
    update.effective_user = MagicMock()
    update.effective_user.id = uid
    if con_callback:
        cq = MagicMock()
        cq.edit_message_reply_markup = AsyncMock()
        update.callback_query = cq
    else:
        update.callback_query = None
    return update


def _make_context(*, es_admin: bool = True) -> MagicMock:
    context = MagicMock()
    repo = MagicMock()
    fl = MagicMock()
    fl.es_admin = es_admin
    repo.buscar_por_telegram_id.return_value = fl
    context.bot_data = {"freelancer_repo": repo}
    context.user_data = {}
    return context


@contextmanager
def _tier_admin() -> Iterator[None]:
    with (
        patch(
            "garay.infraestructura.telegram.handlers.obtener_settings",
            return_value=MagicMock(propietario_telegram_ids="", dev_telegram_ids=""),
        ),
        patch(
            "garay.infraestructura.telegram.handlers.dev_telegram_ids",
            return_value=set(),
        ),
    ):
        yield


class TestFinalizarFlujo:
    @pytest.mark.asyncio
    async def test_limpia_teclado_cuando_hay_callback(self) -> None:
        update = _make_update(con_callback=True)
        with _tier_admin():
            await finalizar_flujo(update, _make_context(), "Listo", GrupoComando.ADMINISTRACION)
        update.callback_query.edit_message_reply_markup.assert_called_once_with(reply_markup=None)

    @pytest.mark.asyncio
    async def test_sin_callback_no_falla(self) -> None:
        update = _make_update(con_callback=False)
        with _tier_admin():
            result = await finalizar_flujo(
                update, _make_context(), "Listo", GrupoComando.ADMINISTRACION
            )
        assert result == ConversationHandler.END
        assert update.effective_message.reply_text.call_count == 2

    @pytest.mark.asyncio
    async def test_envia_mensaje_final_y_submenu(self) -> None:
        update = _make_update(con_callback=True)
        with _tier_admin():
            await finalizar_flujo(
                update, _make_context(), "Freelancer eliminado", GrupoComando.ADMINISTRACION
            )
        calls = update.effective_message.reply_text.call_args_list
        assert calls[0].args[0] == "Freelancer eliminado"
        submenu = calls[1].args[0]
        assert "eliminar_freelancer" in submenu
        assert "/start" in submenu

    @pytest.mark.asyncio
    async def test_teclado_falla_no_rompe(self) -> None:
        update = _make_update(con_callback=True)
        update.callback_query.edit_message_reply_markup.side_effect = TelegramError("gone")
        with _tier_admin():
            result = await finalizar_flujo(
                update, _make_context(), "Listo", GrupoComando.TOURS
            )
        assert result == ConversationHandler.END
        assert update.effective_message.reply_text.call_count == 2

    @pytest.mark.asyncio
    async def test_sin_effective_message_retorna_end(self) -> None:
        update = _make_update(con_callback=True)
        update.effective_message = None
        with _tier_admin():
            result = await finalizar_flujo(
                update, _make_context(), "Listo", GrupoComando.TOURS
            )
        assert result == ConversationHandler.END


class TestCerrarFlujo:
    """cerrar_flujo clears buttons and shows the submenu without a final message."""

    @pytest.mark.asyncio
    async def test_limpia_teclado_y_solo_muestra_submenu(self) -> None:
        update = _make_update(con_callback=True)
        with _tier_admin():
            result = await cerrar_flujo(update, _make_context(), GrupoComando.ADMINISTRACION)
        assert result == ConversationHandler.END
        update.callback_query.edit_message_reply_markup.assert_called_once_with(reply_markup=None)
        assert update.effective_message.reply_text.call_count == 1
        assert "/start" in update.effective_message.reply_text.call_args.args[0]
