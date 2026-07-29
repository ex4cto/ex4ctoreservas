"""Unit tests for the requiere_propietario decorator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Update

from garay.infraestructura.telegram.auth import requiere_propietario

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


def _make_context() -> MagicMock:
    ctx = MagicMock()
    ctx.bot_data = {}
    return ctx


async def _dummy_handler(update: object, context: object) -> int:
    return 99


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_propietario_en_lista_permite_acceso() -> None:
    """User ID in propietario_telegram_ids: inner handler is called."""
    update = _make_update(user_id=111)
    ctx = _make_context()
    wrapped = requiere_propietario(_dummy_handler)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=MagicMock(propietario_telegram_ids="111,222"),
    ):
        result = await wrapped(update, ctx)

    assert result == 99


async def test_usuario_no_en_lista_deniega_acceso() -> None:
    """User ID not in list: reply_text with sin_acceso message, returns None."""
    update = _make_update(user_id=999)
    ctx = _make_context()
    wrapped = requiere_propietario(_dummy_handler)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=MagicMock(propietario_telegram_ids="111,222"),
    ):
        result = await wrapped(update, ctx)

    update.effective_message.reply_text.assert_called_once()
    assert result is None


async def test_lista_vacia_deniega_acceso() -> None:
    """Empty propietario_telegram_ids: fail-safe, denies access."""
    update = _make_update(user_id=111)
    ctx = _make_context()
    wrapped = requiere_propietario(_dummy_handler)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=MagicMock(propietario_telegram_ids=""),
    ):
        result = await wrapped(update, ctx)

    update.effective_message.reply_text.assert_called_once()
    assert result is None


async def test_effective_user_none_devuelve_none() -> None:
    """Channel post with no user: returns None immediately."""
    update = _make_update(user_id=None)
    ctx = _make_context()
    wrapped = requiere_propietario(_dummy_handler)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=MagicMock(propietario_telegram_ids="111"),
    ):
        result = await wrapped(update, ctx)

    assert result is None


async def test_segundo_id_en_lista_permite_acceso() -> None:
    """Second ID in comma-separated list is also granted access."""
    update = _make_update(user_id=222)
    ctx = _make_context()
    wrapped = requiere_propietario(_dummy_handler)

    with patch(
        "garay.infraestructura.telegram.auth.obtener_settings",
        return_value=MagicMock(propietario_telegram_ids="111,222"),
    ):
        result = await wrapped(update, ctx)

    assert result == 99


def test_functools_wraps_preserva_nombre() -> None:
    """@functools.wraps: decorated handler keeps __name__ of the original."""
    wrapped = requiere_propietario(_dummy_handler)
    assert wrapped.__name__ == _dummy_handler.__name__
