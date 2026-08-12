"""Tests for dynamic cmd_start and new cmd_help handler.

cmd_start resolves the caller's tier and replies with render_menu(tier).
cmd_help behaves identically.
Both return ConversationHandler.END (cmd_start is a ConversationHandler entry point).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.handlers import cmd_start


def _make_update(uid: int = 12345) -> MagicMock:
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    update.effective_message = update.message
    update.effective_user = MagicMock()
    update.effective_user.id = uid
    return update


def _make_context(
    *,
    fl_repo_result: MagicMock | None = None,
) -> MagicMock:
    context = MagicMock()
    repo = MagicMock()
    repo.buscar_por_telegram_id.return_value = fl_repo_result
    context.bot_data = {"freelancer_repo": repo}
    context.user_data = {}
    return context


def _freelancer(*, es_admin: bool = False) -> MagicMock:
    fl = MagicMock()
    fl.es_admin = es_admin
    return fl


class TestCmdStartDinamico:
    """cmd_start must reply with the caller-specific menu and return END."""

    @pytest.mark.asyncio
    async def test_freelancer_ve_nueva_venta(self) -> None:
        update = _make_update(uid=999)
        context = _make_context(fl_repo_result=_freelancer(es_admin=False))
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
            result = await cmd_start(update, context)

        assert result == ConversationHandler.END
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "nueva_venta" in text

    @pytest.mark.asyncio
    async def test_freelancer_no_ve_editar_freelancer(self) -> None:
        update = _make_update(uid=999)
        context = _make_context(fl_repo_result=_freelancer(es_admin=False))
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
            await cmd_start(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "editar_freelancer" not in text
        assert "flujo_caja" not in text

    @pytest.mark.asyncio
    async def test_admin_ve_editar_freelancer(self) -> None:
        update = _make_update(uid=888)
        context = _make_context(fl_repo_result=_freelancer(es_admin=True))
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
            await cmd_start(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "editar_freelancer" in text

    @pytest.mark.asyncio
    async def test_admin_no_ve_flujo_caja(self) -> None:
        update = _make_update(uid=888)
        context = _make_context(fl_repo_result=_freelancer(es_admin=True))
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
            await cmd_start(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "flujo_caja" not in text

    @pytest.mark.asyncio
    async def test_propietario_ve_flujo_caja(self) -> None:
        propietario_uid = 777
        update = _make_update(uid=propietario_uid)
        context = _make_context(fl_repo_result=None)
        with (
            patch(
                "garay.infraestructura.telegram.handlers.obtener_settings",
                return_value=MagicMock(
                    propietario_telegram_ids=str(propietario_uid),
                    dev_telegram_ids="",
                ),
            ),
            patch(
                "garay.infraestructura.telegram.handlers.dev_telegram_ids",
                return_value=set(),
            ),
        ):
            result = await cmd_start(update, context)

        assert result == ConversationHandler.END
        text = update.message.reply_text.call_args[0][0]
        assert "flujo_caja" in text

    @pytest.mark.asyncio
    async def test_dev_ve_flujo_caja(self) -> None:
        dev_uid = 111
        update = _make_update(uid=dev_uid)
        context = _make_context(fl_repo_result=None)
        with (
            patch(
                "garay.infraestructura.telegram.handlers.obtener_settings",
                return_value=MagicMock(propietario_telegram_ids="", dev_telegram_ids=""),
            ),
            patch(
                "garay.infraestructura.telegram.handlers.dev_telegram_ids",
                return_value={dev_uid},
            ),
        ):
            await cmd_start(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "flujo_caja" in text

    @pytest.mark.asyncio
    async def test_retorna_conversation_end(self) -> None:
        update = _make_update(uid=999)
        context = _make_context(fl_repo_result=_freelancer(es_admin=False))
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
            result = await cmd_start(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_sin_mensaje_retorna_end_sin_reply(self) -> None:
        update = _make_update(uid=999)
        update.message = None
        context = _make_context(fl_repo_result=None)
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
            result = await cmd_start(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_repo_none_en_bot_data_trata_como_freelancer(self) -> None:
        """When freelancer_repo is absent from bot_data, treat caller as FREELANCER."""
        update = _make_update(uid=555)
        context = MagicMock()
        context.bot_data = {}  # no freelancer_repo
        context.user_data = {}
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
            result = await cmd_start(update, context)

        assert result == ConversationHandler.END
        text = update.message.reply_text.call_args[0][0]
        assert "nueva_venta" in text
        assert "flujo_caja" not in text


class TestCmdHelp:
    """cmd_help must behave identically to cmd_start (same render)."""

    @pytest.mark.asyncio
    async def test_cmd_help_freelancer_ve_nueva_venta(self) -> None:
        from garay.infraestructura.telegram.handlers import cmd_help

        update = _make_update(uid=999)
        context = _make_context(fl_repo_result=_freelancer(es_admin=False))
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
            result = await cmd_help(update, context)

        assert result == ConversationHandler.END
        text = update.message.reply_text.call_args[0][0]
        assert "nueva_venta" in text
        assert "editar_freelancer" not in text

    @pytest.mark.asyncio
    async def test_cmd_help_propietario_ve_flujo_caja(self) -> None:
        from garay.infraestructura.telegram.handlers import cmd_help

        propietario_uid = 777
        update = _make_update(uid=propietario_uid)
        context = _make_context(fl_repo_result=None)
        with (
            patch(
                "garay.infraestructura.telegram.handlers.obtener_settings",
                return_value=MagicMock(
                    propietario_telegram_ids=str(propietario_uid),
                    dev_telegram_ids="",
                ),
            ),
            patch(
                "garay.infraestructura.telegram.handlers.dev_telegram_ids",
                return_value=set(),
            ),
        ):
            result = await cmd_help(update, context)

        assert result == ConversationHandler.END
        text = update.message.reply_text.call_args[0][0]
        assert "flujo_caja" in text
