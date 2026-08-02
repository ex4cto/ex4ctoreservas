"""Tests for _post_init menu setup — graceful handling of 'Chat not found'."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import MagicMock

from telegram import BotCommandScopeChat
from telegram.error import BadRequest

from garay.infraestructura.telegram.bot import _post_init


def _make_app(propietario_ids: str) -> MagicMock:
    """Build a fake PTB Application whose per-chat set_my_commands always fails.

    The default-scope call succeeds; the per-chat call raises BadRequest, exactly
    like Telegram does for a configured user who never started a chat with the bot.
    """
    app = MagicMock()

    async def _fake_set(_commands: Any, scope: Any = None) -> bool:
        if isinstance(scope, BotCommandScopeChat):
            raise BadRequest("Chat not found")
        return True

    app.bot.set_my_commands = _fake_set

    repo = MagicMock()
    repo.listar_activos.return_value = []
    app.bot_data = {"freelancer_repo": repo}
    return app


def test_post_init_chat_not_found_no_crashea(monkeypatch: Any) -> None:
    """A per-chat 'Chat not found' must never abort startup."""
    settings = MagicMock()
    settings.propietario_telegram_ids = "111"
    settings.dev_telegram_ids = ""
    monkeypatch.setattr(
        "garay.infraestructura.telegram.bot.obtener_settings", lambda: settings
    )

    # Must not raise.
    asyncio.run(_post_init(_make_app("111")))


def test_post_init_chat_not_found_warning_sin_traceback(
    monkeypatch: Any, caplog: Any
) -> None:
    """The failure is logged as a plain warning WITHOUT an exception traceback,
    so an expected condition does not look like a crash or bury real errors."""
    settings = MagicMock()
    settings.propietario_telegram_ids = "111"
    settings.dev_telegram_ids = ""
    monkeypatch.setattr(
        "garay.infraestructura.telegram.bot.obtener_settings", lambda: settings
    )

    with caplog.at_level(logging.WARNING, logger="garay.infraestructura.telegram.bot"):
        asyncio.run(_post_init(_make_app("111")))

    menu_warnings = [
        r for r in caplog.records if "No se pudo fijar el menú" in r.getMessage()
    ]
    assert len(menu_warnings) == 1
    assert "111" in menu_warnings[0].getMessage()
    # The noise fix: no full traceback attached to an expected condition.
    assert menu_warnings[0].exc_info is None
