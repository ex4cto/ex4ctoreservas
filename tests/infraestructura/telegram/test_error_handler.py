"""Tests for the global PTB error handler (_manejar_error) — TDD."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update

from garay.infraestructura.telegram.bot import _manejar_error
from garay.mensajes.catalogo import obtener_mensaje


def _settings(dev_ids: str) -> MagicMock:
    s = MagicMock()
    s.dev_telegram_ids = dev_ids
    return s


def _context() -> MagicMock:
    ctx = MagicMock()
    ctx.error = RuntimeError("boom")
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    return ctx


class TestManejarError:
    @pytest.mark.asyncio
    async def test_notifica_usuario_contactar_ryan(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(
            "garay.infraestructura.telegram.bot.obtener_settings",
            lambda: _settings(""),
        )
        update = MagicMock(spec=Update)
        update.effective_message = AsyncMock()
        ctx = _context()

        await _manejar_error(update, ctx)

        update.effective_message.reply_text.assert_called_once_with(
            obtener_mensaje("error.contactar_soporte")
        )

    @pytest.mark.asyncio
    async def test_reporta_a_cada_dev_en_texto_plano(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(
            "garay.infraestructura.telegram.bot.obtener_settings",
            lambda: _settings("111,222"),
        )
        update = MagicMock(spec=Update)
        update.effective_message = None
        ctx = _context()

        await _manejar_error(update, ctx)

        assert ctx.bot.send_message.call_count == 2
        ids = {c.kwargs["chat_id"] for c in ctx.bot.send_message.call_args_list}
        assert ids == {111, 222}
        for c in ctx.bot.send_message.call_args_list:
            assert c.kwargs.get("parse_mode") is None

    @pytest.mark.asyncio
    async def test_reporte_dev_incluye_info_del_error(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(
            "garay.infraestructura.telegram.bot.obtener_settings",
            lambda: _settings("111"),
        )
        update = MagicMock(spec=Update)
        update.effective_message = None
        ctx = _context()

        await _manejar_error(update, ctx)

        texto = ctx.bot.send_message.call_args.kwargs["text"]
        assert "boom" in texto

    @pytest.mark.asyncio
    async def test_update_no_es_update_no_crashea(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(
            "garay.infraestructura.telegram.bot.obtener_settings",
            lambda: _settings("111"),
        )
        ctx = _context()

        # Must not raise even when update is not an Update instance.
        await _manejar_error("not-an-update", ctx)

        ctx.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallo_al_notificar_usuario_no_impide_reporte_dev(
        self, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr(
            "garay.infraestructura.telegram.bot.obtener_settings",
            lambda: _settings("111"),
        )
        update = MagicMock(spec=Update)
        update.effective_message = AsyncMock()
        update.effective_message.reply_text = AsyncMock(
            side_effect=RuntimeError("telegram down")
        )
        ctx = _context()

        # Must not raise; dev report must still go out.
        await _manejar_error(update, ctx)

        ctx.bot.send_message.assert_called_once()


def test_crear_aplicacion_registra_error_handler() -> None:
    from garay.infraestructura.telegram.bot import crear_aplicacion

    app = crear_aplicacion("123456:FAKETOKEN")

    assert _manejar_error in app.error_handlers


class TestManejarErrorRed:
    @pytest.mark.asyncio
    async def test_network_error_no_notifica_ni_dev_ni_usuario(self, monkeypatch: Any) -> None:
        """Transient NetworkError must be ignored (no dev report, no user message)."""
        from telegram.error import NetworkError

        monkeypatch.setattr(
            "garay.infraestructura.telegram.bot.obtener_settings",
            lambda: _settings("111,222"),
        )
        update = MagicMock(spec=Update)
        update.effective_message = AsyncMock()
        ctx = _context()
        ctx.error = NetworkError("httpx.ReadError: ")

        await _manejar_error(update, ctx)

        ctx.bot.send_message.assert_not_called()
        update.effective_message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_timedout_tambien_se_ignora(self, monkeypatch: Any) -> None:
        """TimedOut (subclass of NetworkError) is also ignored."""
        from telegram.error import TimedOut

        monkeypatch.setattr(
            "garay.infraestructura.telegram.bot.obtener_settings",
            lambda: _settings("111"),
        )
        ctx = _context()
        ctx.error = TimedOut()

        await _manejar_error("not-an-update", ctx)

        ctx.bot.send_message.assert_not_called()
