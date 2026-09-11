"""Tests for NotificadorGrupoTelegram — no real HTTP calls."""

from __future__ import annotations

import io
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


def _make_http_error_body(code: int, body: dict[str, object]) -> urllib.error.HTTPError:
    """HTTPError whose .read() returns the given JSON body (e.g. migrate_to_chat_id)."""
    raw = json.dumps(body).encode("utf-8")
    return urllib.error.HTTPError(
        url="https://api.telegram.org",
        code=code,
        msg="Bad Request",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(raw),
    )


def _chat_ids_enviados(mock_open: MagicMock) -> list[str]:
    ids: list[str] = []
    for call in mock_open.call_args_list:
        ids.append(json.loads(call[0][0].data.decode("utf-8"))["chat_id"])
    return ids


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

    def test_migracion_reintenta_al_id_nuevo_y_no_lanza(self) -> None:
        """400 con migrate_to_chat_id → reintenta al ID nuevo y NO lanza excepción."""
        notificador = NotificadorGrupoTelegram(token=_TOKEN)
        mig = _make_http_error_body(400, {"parameters": {"migrate_to_chat_id": -1009999}})
        ok = _make_response()

        # sin dev_ids: envío al viejo (mig) → reintento al nuevo (ok)
        with patch("urllib.request.urlopen", side_effect=[mig, ok]) as mock_open:
            notificador.notificar(_MENSAJE, _GRUPO)  # no debe lanzar

        assert _chat_ids_enviados(mock_open)[-1] == "-1009999"

    def test_migracion_alerta_a_devs_con_id_nuevo(self) -> None:
        """En migración, se alerta a cada dev con el ID nuevo y GARAY_GRUPO_ID."""
        notificador = NotificadorGrupoTelegram(token=_TOKEN, dev_ids=[555])
        mig = _make_http_error_body(400, {"parameters": {"migrate_to_chat_id": -1009999}})
        ok_dev = _make_response()
        ok_retry = _make_response()

        with patch("urllib.request.urlopen", side_effect=[mig, ok_dev, ok_retry]) as mock_open:
            notificador.notificar(_MENSAJE, _GRUPO)

        # se envió un mensaje al dev (555) mencionando el ID nuevo y la variable
        textos = {
            json.loads(c[0][0].data.decode("utf-8"))["chat_id"]: json.loads(
                c[0][0].data.decode("utf-8")
            )["text"]
            for c in mock_open.call_args_list
        }
        assert "555" in textos
        assert "-1009999" in textos["555"]
        assert "GARAY_GRUPO_ID" in textos["555"]

    def test_migracion_se_recuerda_en_memoria(self) -> None:
        """Tras una migración, los envíos siguientes van directo al ID nuevo."""
        notificador = NotificadorGrupoTelegram(token=_TOKEN)
        mig = _make_http_error_body(400, {"parameters": {"migrate_to_chat_id": -1009999}})

        with patch("urllib.request.urlopen", side_effect=[mig, _make_response()]):
            notificador.notificar(_MENSAJE, _GRUPO)

        with patch("urllib.request.urlopen", return_value=_make_response()) as mock_open2:
            notificador.notificar(_MENSAJE, _GRUPO)

        assert _chat_ids_enviados(mock_open2) == ["-1009999"]

    def test_notificar_error_inesperado_se_envuelve(self) -> None:
        """Any unexpected error (e.g. ValueError from a malformed URL) is wrapped as a
        notifier error and never propagates raw — callers such as the webhook rely on
        this to preserve their always-200 contract."""
        notificador = NotificadorGrupoTelegram(token=_TOKEN)

        with (
            patch("urllib.request.urlopen", side_effect=ValueError("unknown url type")),
            pytest.raises((NotificadorError, NotificadorNoDisponible)),
        ):
            notificador.notificar(_MENSAJE, _GRUPO)
