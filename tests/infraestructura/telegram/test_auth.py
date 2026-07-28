"""Unit tests for the requiere_rol decorator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from telegram import Update
from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.auth import requiere_admin, requiere_rol

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_update(user_id: int | None = 123) -> MagicMock:
    update = MagicMock(spec=Update)
    if user_id is None:
        update.effective_user = None
    else:
        update.effective_user = MagicMock()
        update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    return update


def _make_context(repo: object | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.bot_data = {}
    if repo is not None:
        ctx.bot_data["freelancer_repo"] = repo
    return ctx


def _make_repo(found: bool = True) -> MagicMock:
    repo = MagicMock()
    repo.buscar_por_telegram_id.return_value = MagicMock() if found else None
    return repo


# ---------------------------------------------------------------------------
# A trivial async handler to wrap
# ---------------------------------------------------------------------------


async def _dummy_handler(update: object, context: object) -> int:
    return 42


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_usuario_registrado_permite_acceso() -> None:
    """Registered user: inner handler is called and its return value propagates."""
    repo = _make_repo(found=True)
    update = _make_update(user_id=123)
    context = _make_context(repo=repo)

    wrapped = requiere_rol(_dummy_handler)
    result = await wrapped(update, context)

    repo.buscar_por_telegram_id.assert_called_once_with(123)
    assert result == 42


async def test_usuario_no_registrado_deniega_acceso() -> None:
    """Unregistered user: reply_text called with denial message, returns END."""
    repo = _make_repo(found=False)
    update = _make_update(user_id=456)
    context = _make_context(repo=repo)

    wrapped = requiere_rol(_dummy_handler)
    result = await wrapped(update, context)

    update.effective_message.reply_text.assert_called_once_with(
        "No estás registrado como freelancer."
    )
    assert result == ConversationHandler.END


async def test_effective_user_none_devuelve_end() -> None:
    """Channel post with no user: returns END without touching repo."""
    repo = _make_repo(found=True)
    update = _make_update(user_id=None)
    context = _make_context(repo=repo)

    wrapped = requiere_rol(_dummy_handler)
    result = await wrapped(update, context)

    repo.buscar_por_telegram_id.assert_not_called()
    assert result == ConversationHandler.END


async def test_repo_ausente_en_bot_data_devuelve_end() -> None:
    """Missing freelancer_repo in bot_data: returns END (wiring error)."""
    update = _make_update(user_id=123)
    context = _make_context(repo=None)  # no repo injected

    wrapped = requiere_rol(_dummy_handler)
    result = await wrapped(update, context)

    assert result == ConversationHandler.END


def test_functools_wraps_preserva_nombre() -> None:
    """@functools.wraps: decorated handler keeps __name__ of the original."""
    wrapped = requiere_rol(_dummy_handler)
    assert wrapped.__name__ == _dummy_handler.__name__


# ---------------------------------------------------------------------------
# Tests for requiere_admin
# ---------------------------------------------------------------------------


def _make_repo_admin(found: bool = True, es_admin: bool = False) -> MagicMock:
    repo = MagicMock()
    if found:
        freelancer = MagicMock()
        freelancer.es_admin = es_admin
        repo.buscar_por_telegram_id.return_value = freelancer
    else:
        repo.buscar_por_telegram_id.return_value = None
    return repo


async def test_requiere_admin_no_freelancer() -> None:
    """buscar_por_telegram_id returns None → reply + return None."""
    repo = _make_repo_admin(found=False)
    update = _make_update(user_id=123)
    context = _make_context(repo=repo)

    wrapped = requiere_admin(_dummy_handler)
    result = await wrapped(update, context)

    update.effective_message.reply_text.assert_called_once_with(
        "No estás registrado como freelancer."
    )
    assert result is None


async def test_requiere_admin_no_es_admin() -> None:
    """Freelancer found but es_admin=False → reply + return None."""
    repo = _make_repo_admin(found=True, es_admin=False)
    update = _make_update(user_id=123)
    context = _make_context(repo=repo)

    wrapped = requiere_admin(_dummy_handler)
    result = await wrapped(update, context)

    update.effective_message.reply_text.assert_called_once_with(
        "Este comando es solo para administradores."
    )
    assert result is None


async def test_requiere_admin_ok() -> None:
    """Freelancer found and es_admin=True → handler called and return value propagates."""
    repo = _make_repo_admin(found=True, es_admin=True)
    update = _make_update(user_id=123)
    context = _make_context(repo=repo)

    wrapped = requiere_admin(_dummy_handler)
    result = await wrapped(update, context)

    repo.buscar_por_telegram_id.assert_called_once_with(123)
    assert result == 42
