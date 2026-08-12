"""Unit tests for the requiere_rol decorator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Update
from telegram.ext import ConversationHandler

from garay.dominio.puertos.repositorios import FreelancerRepository
from garay.infraestructura.telegram.auth import (
    dev_telegram_ids,
    requiere_admin,
    requiere_admin_conv,
    requiere_rol,
)

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


# ---------------------------------------------------------------------------
# Tests for requiere_admin_conv
# ---------------------------------------------------------------------------


class TestRequiereAdminConv:
    """requiere_admin_conv must return ConversationHandler.END (not None) on deny."""

    def _make_repo(self, freelancer: object | None = None) -> MagicMock:
        repo = MagicMock(spec=FreelancerRepository)
        repo.buscar_por_telegram_id.return_value = freelancer
        return repo

    async def test_sin_usuario_retorna_end(self) -> None:
        @requiere_admin_conv
        async def handler(update: object, context: object) -> int:
            return 99

        update = MagicMock()
        update.effective_user = None
        context = MagicMock()
        result = await handler(update, context)
        assert result == ConversationHandler.END

    async def test_no_registrado_retorna_end(self) -> None:
        @requiere_admin_conv
        async def handler(update: object, context: object) -> int:
            return 99

        update = MagicMock()
        update.effective_user = MagicMock(id=999)
        update.effective_message = AsyncMock()
        context = MagicMock()
        context.bot_data = {"freelancer_repo": self._make_repo(None)}
        with patch("garay.infraestructura.telegram.auth._es_dev", return_value=False):
            result = await handler(update, context)
        assert result == ConversationHandler.END

    async def test_no_admin_retorna_end(self) -> None:
        import uuid

        from garay.dominio.freelancers.entidades import Freelancer

        freelancer = Freelancer(id=uuid.uuid4(), nombre="Juan", es_admin=False)

        @requiere_admin_conv
        async def handler(update: object, context: object) -> int:
            return 99

        update = MagicMock()
        update.effective_user = MagicMock(id=123)
        update.effective_message = AsyncMock()
        context = MagicMock()
        context.bot_data = {"freelancer_repo": self._make_repo(freelancer)}
        with patch("garay.infraestructura.telegram.auth._es_dev", return_value=False):
            result = await handler(update, context)
        assert result == ConversationHandler.END

    async def test_admin_llama_handler(self) -> None:
        import uuid

        from garay.dominio.freelancers.entidades import Freelancer

        freelancer = Freelancer(id=uuid.uuid4(), nombre="Garay", es_admin=True)

        @requiere_admin_conv
        async def handler(update: object, context: object) -> int:
            return 42

        update = MagicMock()
        update.effective_user = MagicMock(id=123)
        context = MagicMock()
        context.bot_data = {"freelancer_repo": self._make_repo(freelancer)}
        with patch("garay.infraestructura.telegram.auth._es_dev", return_value=False):
            result = await handler(update, context)
        assert result == 42


# ---------------------------------------------------------------------------
# Tests for dev_telegram_ids() helper
# ---------------------------------------------------------------------------


_PATCH_SETTINGS = "garay.infraestructura.telegram.auth.obtener_settings"


class TestDevTelegramIds:
    def test_parses_multiple_ids(self) -> None:
        settings_mock = MagicMock()
        settings_mock.dev_telegram_ids = "111, 222"
        with patch(_PATCH_SETTINGS, return_value=settings_mock):
            result = dev_telegram_ids()
        assert result == {111, 222}

    def test_single_id(self) -> None:
        settings_mock = MagicMock()
        settings_mock.dev_telegram_ids = "999"
        with patch(_PATCH_SETTINGS, return_value=settings_mock):
            result = dev_telegram_ids()
        assert result == {999}

    def test_empty_string_returns_empty_set(self) -> None:
        settings_mock = MagicMock()
        settings_mock.dev_telegram_ids = ""
        with patch(_PATCH_SETTINGS, return_value=settings_mock):
            result = dev_telegram_ids()
        assert result == set()

    def test_whitespace_only_returns_empty_set(self) -> None:
        settings_mock = MagicMock()
        settings_mock.dev_telegram_ids = "   "
        with patch(_PATCH_SETTINGS, return_value=settings_mock):
            result = dev_telegram_ids()
        assert result == set()

    def test_strips_whitespace_around_ids(self) -> None:
        settings_mock = MagicMock()
        settings_mock.dev_telegram_ids = "  100 , 200  , 300"
        with patch(_PATCH_SETTINGS, return_value=settings_mock):
            result = dev_telegram_ids()
        assert result == {100, 200, 300}
