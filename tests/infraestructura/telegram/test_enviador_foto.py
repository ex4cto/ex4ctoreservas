"""Unit tests for EnviadorFotoTelegram.

Uses unittest.mock to patch urllib.request.urlopen so no real HTTP calls are made.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from io import BytesIO
from unittest.mock import MagicMock, call, patch

import pytest

from garay.infraestructura.telegram.enviador_foto import EnviadorFotoTelegram


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_response(payload: dict[str, object] | None = None) -> MagicMock:
    """Build a mock urllib context-manager response for a 200 OK."""
    if payload is None:
        payload = {"ok": True, "result": {"message_id": 1}}
    body = json.dumps(payload).encode()
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = body
    resp.status = 200
    return resp


def _http_error(status: int, payload: dict[str, object]) -> urllib.error.HTTPError:
    """Build a urllib.error.HTTPError with a JSON body."""
    body = json.dumps(payload).encode()
    fp = BytesIO(body)
    return urllib.error.HTTPError(
        url="https://api.telegram.org/bot.../sendPhoto",
        code=status,
        msg="Bad Request",
        hdrs={},  # type: ignore[arg-type]
        fp=fp,
    )


_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEnviadorFotoTelegram:
    @pytest.mark.asyncio
    async def test_envia_foto_llama_send_photo(self) -> None:
        """enviar() POSTs to sendPhoto with correct token, chat_id, and photo bytes."""
        enviador = EnviadorFotoTelegram(token="bot123:TOKEN")

        with patch("urllib.request.urlopen", return_value=_ok_response()) as mock_open:
            await enviador.enviar(_FAKE_PNG, "-1001234567890")

        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        # Must target the sendPhoto endpoint
        assert "sendPhoto" in req.get_full_url()
        assert "bot123:TOKEN" in req.get_full_url()
        # Body must contain the group id and photo data
        data: bytes = req.data
        assert b"-1001234567890" in data
        assert b"photo" in data

    @pytest.mark.asyncio
    async def test_supergrupo_migracion_reintenta_con_nuevo_chat_id(self) -> None:
        """On migrate_to_chat_id error, retries with the new chat_id and succeeds."""
        enviador = EnviadorFotoTelegram(token="bot123:TOKEN")

        migrate_exc = _http_error(
            400,
            {
                "ok": False,
                "error_code": 400,
                "description": "group chat was upgraded to a supergroup chat",
                "parameters": {"migrate_to_chat_id": -1009999999999},
            },
        )

        call_count = 0

        def side_effect(req: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise migrate_exc
            return _ok_response()

        with patch("urllib.request.urlopen", side_effect=side_effect) as mock_open:
            await enviador.enviar(_FAKE_PNG, "-1001111111111")

        assert mock_open.call_count == 2
        # Second call must use the new chat_id
        second_req = mock_open.call_args_list[1][0][0]
        assert b"-1009999999999" in second_req.data

    @pytest.mark.asyncio
    async def test_error_telegram_no_relacionado_lanza_excepcion(self) -> None:
        """Non-migration Telegram errors raise RuntimeError."""
        enviador = EnviadorFotoTelegram(token="bot123:TOKEN")

        error_exc = _http_error(
            403,
            {"ok": False, "error_code": 403, "description": "Forbidden: bot was kicked"},
        )

        with patch("urllib.request.urlopen", side_effect=error_exc):
            with pytest.raises(RuntimeError):
                await enviador.enviar(_FAKE_PNG, "-1001234567890")
