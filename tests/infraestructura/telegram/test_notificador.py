"""Tests for NotificadorGrupoTelegram — no real HTTP calls."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from garay.infraestructura.telegram.errores import NotificadorError, NotificadorNoDisponible
from garay.infraestructura.telegram.notificador import NotificadorGrupoTelegram

_TOKEN = "test-bot-token"
_GRUPO = "-1001234567890"
_MENSAJE = "Nueva venta registrada"


def _make_response(status: int = 200) -> MagicMock:
    """Build a mock urllib context-manager response."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ok": true}'
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://api.telegram.org",
        code=code,
        msg="Bad Request",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )


class TestNotificadorGrupoTelegram:
    def test_notificar_llama_api_correctamente(self) -> None:
        """URL contains the token and payload has the required fields."""
        notificador = NotificadorGrupoTelegram(token=_TOKEN)
        mock_resp = _make_response()

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            notificador.notificar(_MENSAJE, _GRUPO)

        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]

        assert f"bot{_TOKEN}" in req.full_url
        assert "sendMessage" in req.full_url

        body = json.loads(req.data.decode("utf-8"))
        assert body["chat_id"] == _GRUPO
        assert body["text"] == _MENSAJE
        assert body["parse_mode"] == "HTML"

    def test_notificar_exito_no_lanza_excepcion(self) -> None:
        """Happy path: 200 response raises no exception and returns None."""
        notificador = NotificadorGrupoTelegram(token=_TOKEN)
        mock_resp = _make_response(status=200)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            notificador.notificar(_MENSAJE, _GRUPO)  # must not raise

    def test_notificar_error_conexion_lanza_no_disponible(self) -> None:
        """URLError (network failure) raises NotificadorNoDisponible."""
        notificador = NotificadorGrupoTelegram(token=_TOKEN)
        url_error = urllib.error.URLError("Connection refused")

        with (
            patch("urllib.request.urlopen", side_effect=url_error),
            pytest.raises(NotificadorNoDisponible),
        ):
            notificador.notificar(_MENSAJE, _GRUPO)

    def test_notificar_error_http_lanza_error(self) -> None:
        """HTTPError with non-2xx status raises NotificadorError with the code."""
        notificador = NotificadorGrupoTelegram(token=_TOKEN)
        http_error = _make_http_error(400)

        with (
            patch("urllib.request.urlopen", side_effect=http_error),
            pytest.raises(NotificadorError, match="400"),
        ):
            notificador.notificar(_MENSAJE, _GRUPO)

    def test_mensaje_vacio_se_envia_igual(self) -> None:
        """Empty string mensaje is sent without validation — port doesn't restrict content."""
        notificador = NotificadorGrupoTelegram(token=_TOKEN)
        mock_resp = _make_response()

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            notificador.notificar("", _GRUPO)

        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["text"] == ""
