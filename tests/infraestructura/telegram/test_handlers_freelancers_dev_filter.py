"""Tests for dev-user exclusion filter in freelancer management handlers.

These tests verify that users whose telegram_user_id matches a configured
dev ID are excluded from the freelancer management listings shown to
admin/propietario, without affecting sales participant pickers.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.freelancers.entidades import Freelancer
from garay.infraestructura.telegram.handlers_freelancers import (
    EDITAR_SELECCIONAR,
    EF_SELECCIONAR,
    cmd_editar_freelancer,
    cmd_eliminar_freelancer,
    cmd_listar_freelancers,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEV_ID = 99999


def _make_settings_with_dev(dev_id: int = _DEV_ID) -> MagicMock:
    settings = MagicMock()
    settings.dev_telegram_ids = str(dev_id)
    return settings


def _make_settings_no_dev() -> MagicMock:
    settings = MagicMock()
    settings.dev_telegram_ids = ""
    return settings


def _make_freelancer(
    nombre: str = "Ana",
    activo: bool = True,
    telegram_user_id: int | None = None,
) -> Freelancer:
    return Freelancer(
        id=uuid.uuid4(),
        nombre=nombre,
        activo=activo,
        telegram_user_id=telegram_user_id,
        es_admin=False,
    )


def _make_update() -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock(id=1)
    update.effective_message = AsyncMock()
    update.callback_query = None
    return update


def _make_context(freelancers: list[Freelancer]) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    repo = MagicMock()
    repo.listar_todos.return_value = list(freelancers)
    repo.listar_activos.return_value = [f for f in freelancers if f.activo]
    ctx.bot_data = {"freelancer_repo": repo}
    return ctx


# ---------------------------------------------------------------------------
# cmd_listar_freelancers — dev excluded from list message
# ---------------------------------------------------------------------------


class TestCmdListarFreelancersDevFilter:
    @pytest.mark.asyncio
    async def test_dev_freelancer_excluded_from_message(self) -> None:
        """A freelancer whose telegram_user_id is a dev id must NOT appear in the listing."""
        dev_fl = _make_freelancer("DevUser", telegram_user_id=_DEV_ID)
        regular_fl = _make_freelancer("Regular")
        update = _make_update()
        ctx = _make_context([dev_fl, regular_fl])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_with_dev(),
        ):
            await cmd_listar_freelancers.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        msg = update.effective_message.reply_text.call_args[0][0]
        assert "Regular" in msg
        assert "DevUser" not in msg

    @pytest.mark.asyncio
    async def test_freelancer_with_none_telegram_id_kept(self) -> None:
        """A freelancer with telegram_user_id=None is not a dev and must stay in listing."""
        none_fl = _make_freelancer("NoneUser", telegram_user_id=None)
        update = _make_update()
        ctx = _make_context([none_fl])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_with_dev(),
        ):
            await cmd_listar_freelancers.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        msg = update.effective_message.reply_text.call_args[0][0]
        assert "NoneUser" in msg

    @pytest.mark.asyncio
    async def test_all_devs_shows_empty_list_message(self) -> None:
        """When all freelancers are devs the empty-list message fires."""
        dev_fl = _make_freelancer("DevUser", telegram_user_id=_DEV_ID)
        update = _make_update()
        ctx = _make_context([dev_fl])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_with_dev(),
        ):
            await cmd_listar_freelancers.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        msg = update.effective_message.reply_text.call_args[0][0]
        # must show the empty-list message, not a listing with the dev
        assert "DevUser" not in msg
        assert "No hay freelancers" in msg

    @pytest.mark.asyncio
    async def test_no_dev_ids_configured_shows_all(self) -> None:
        """When no dev ids are configured no freelancer is filtered out."""
        fl = _make_freelancer("Regular", telegram_user_id=_DEV_ID)
        update = _make_update()
        ctx = _make_context([fl])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_no_dev(),
        ):
            await cmd_listar_freelancers.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        msg = update.effective_message.reply_text.call_args[0][0]
        assert "Regular" in msg


# ---------------------------------------------------------------------------
# cmd_eliminar_freelancer — dev excluded from active list keyboard
# ---------------------------------------------------------------------------


class TestCmdEliminarFreelancerDevFilter:
    @pytest.mark.asyncio
    async def test_dev_freelancer_excluded_from_keyboard(self) -> None:
        """A dev freelancer must NOT appear as a button in the eliminate keyboard."""
        dev_fl = _make_freelancer("DevUser", activo=True, telegram_user_id=_DEV_ID)
        regular_fl = _make_freelancer("Regular", activo=True)
        update = _make_update()
        ctx = _make_context([dev_fl, regular_fl])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_with_dev(),
        ):
            result = await cmd_eliminar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == EF_SELECCIONAR
        call_kwargs = update.effective_message.reply_text.call_args
        markup = call_kwargs.kwargs.get("reply_markup") or call_kwargs[1].get("reply_markup")
        buttons_text = " ".join(btn.text for row in markup.inline_keyboard for btn in row)
        assert "Regular" in buttons_text
        assert "DevUser" not in buttons_text

    @pytest.mark.asyncio
    async def test_dev_with_none_telegram_kept(self) -> None:
        """An active freelancer with telegram_user_id=None must stay in the eliminate list."""
        none_fl = _make_freelancer("NoneUser", activo=True, telegram_user_id=None)
        update = _make_update()
        ctx = _make_context([none_fl])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_with_dev(),
        ):
            result = await cmd_eliminar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == EF_SELECCIONAR
        call_kwargs = update.effective_message.reply_text.call_args
        markup = call_kwargs.kwargs.get("reply_markup") or call_kwargs[1].get("reply_markup")
        buttons_text = " ".join(btn.text for row in markup.inline_keyboard for btn in row)
        assert "NoneUser" in buttons_text

    @pytest.mark.asyncio
    async def test_all_active_are_devs_shows_empty_state(self) -> None:
        """When all active freelancers are devs the empty-state branch fires."""
        dev_fl = _make_freelancer("DevUser", activo=True, telegram_user_id=_DEV_ID)
        update = _make_update()
        ctx = _make_context([dev_fl])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_with_dev(),
        ):
            result = await cmd_eliminar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# cmd_editar_freelancer — dev excluded from all-freelancers keyboard
# ---------------------------------------------------------------------------


class TestCmdEditarFreelancerDevFilter:
    @pytest.mark.asyncio
    async def test_dev_freelancer_excluded_from_edit_keyboard(self) -> None:
        """A dev freelancer must NOT appear as a button in the edit keyboard."""
        dev_fl = _make_freelancer("DevUser", telegram_user_id=_DEV_ID)
        regular_fl = _make_freelancer("Regular")
        update = _make_update()
        ctx = _make_context([dev_fl, regular_fl])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_with_dev(),
        ):
            result = await cmd_editar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == EDITAR_SELECCIONAR
        call_kwargs = update.effective_message.reply_text.call_args
        markup = call_kwargs.kwargs.get("reply_markup") or call_kwargs[1].get("reply_markup")
        buttons_text = " ".join(btn.text for row in markup.inline_keyboard for btn in row)
        assert "Regular" in buttons_text
        assert "DevUser" not in buttons_text

    @pytest.mark.asyncio
    async def test_dev_with_none_telegram_kept_in_edit(self) -> None:
        """An freelancer with telegram_user_id=None must stay in the edit list."""
        none_fl = _make_freelancer("NoneUser", telegram_user_id=None)
        update = _make_update()
        ctx = _make_context([none_fl])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_with_dev(),
        ):
            result = await cmd_editar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == EDITAR_SELECCIONAR
        call_kwargs = update.effective_message.reply_text.call_args
        markup = call_kwargs.kwargs.get("reply_markup") or call_kwargs[1].get("reply_markup")
        buttons_text = " ".join(btn.text for row in markup.inline_keyboard for btn in row)
        assert "NoneUser" in buttons_text

    @pytest.mark.asyncio
    async def test_all_are_devs_shows_empty_state(self) -> None:
        """When all freelancers are devs the empty-state branch fires."""
        dev_fl = _make_freelancer("DevUser", telegram_user_id=_DEV_ID)
        update = _make_update()
        ctx = _make_context([dev_fl])

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_with_dev(),
        ):
            result = await cmd_editar_freelancer.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == ConversationHandler.END
