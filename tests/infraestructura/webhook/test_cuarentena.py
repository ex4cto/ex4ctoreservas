"""Tests for webhook quarantine + dev-only alert behavior.

Covers:
- Quarantining unparseable emails (ingreso and egreso paths).
- Dev-only alerts: dev IDs get a technical HTML alert; grupo_id NEVER receives
  a parse-failure alert (owner decision: group alerts on parse failure removed).
- Alert failures (NotificadorError) never break the 200 response or persistence.
- Duplicate quarantine (IntegrityError) is swallowed gracefully.
- Empty dev_telegram_ids produces no alert calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from garay.aplicacion.webhook.app import crear_app
from garay.infraestructura.telegram.errores import NotificadorError
from garay.infraestructura.webhook.alertas import construir_alerta_dev
from tests.infraestructura.webhook.conftest import _SECRET

# ---------------------------------------------------------------------------
# Shared payloads
# ---------------------------------------------------------------------------

_PAYLOAD_BANCOLOMBIA_INGRESO = {
    "message_id": "quar-ing-001",
    "remitente_email": "alertas@notificacionesbancolombia.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Transferencia recibida",
    "cuerpo_html": "",
    "cuerpo_texto": (
        "Recibiste una transferencia por $500,000 de Carlos Gomez "
        "en tu cuenta **5643, el 15/07/26 a las 10:30"
    ),
}

_PAYLOAD_BANCOLOMBIA_EGRESO = {
    "message_id": "quar-egr-001",
    "remitente_email": "alertas@notificacionesbancolombia.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Compra realizada",
    "cuerpo_html": "",
    "cuerpo_texto": (
        "Bancolombia: Compraste $69.328,00 en MOVISTAR PAGOSEPAYCO con tu T.Deb *9283, "
        "el 27/07/2026 a las 18:25."
    ),
}

_DEV_IDS_STR = "111111111,222222222"
_GRUPO_ID = "-100987654321"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(
    mock_ingreso_repo: MagicMock,
    mock_egreso_repo: MagicMock,
    mock_correo_repo: MagicMock,
    mock_notificador: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    *,
    dev_ids: str = _DEV_IDS_STR,
    grupo_id: str = _GRUPO_ID,
) -> TestClient:
    monkeypatch.setenv("GARAY_FORWARD_EMAIL_SECRET", _SECRET)
    monkeypatch.setenv("GARAY_MONEDA_PREDETERMINADA", "COP")
    monkeypatch.setenv("GARAY_DEV_TELEGRAM_IDS", dev_ids)
    monkeypatch.setenv("GARAY_GRUPO_ID", grupo_id)
    monkeypatch.setenv("GARAY_TELEGRAM_BOT_TOKEN", "fake-token")
    import garay.config.settings as _settings_mod

    _settings_mod.obtener_settings.cache_clear()
    app = crear_app(
        ingreso_repo=mock_ingreso_repo,
        egreso_repo=mock_egreso_repo,
        correo_repo=mock_correo_repo,
        notificador=mock_notificador,
    )
    return TestClient(app)


# ---------------------------------------------------------------------------
# Route quarantine tests
# ---------------------------------------------------------------------------


def test_ingreso_parse_error_cuarentena_y_200(
    mock_ingreso_repo: MagicMock,
    mock_egreso_repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When parser raises ErrorParseoBanco (ingreso path), correo_repo.guardar is called
    with the right fields, and the route still returns 200."""
    mock_correo_repo = MagicMock()
    mock_notificador = MagicMock()

    client = _make_client(
        mock_ingreso_repo,
        mock_egreso_repo,
        mock_correo_repo,
        mock_notificador,
        monkeypatch,
    )

    from garay.infraestructura.webhook.parser.base import ErrorParseoBanco

    with patch(
        "garay.infraestructura.webhook.rutas.obtener_parser",
        side_effect=ErrorParseoBanco("parseo fallido"),
    ):
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_BANCOLOMBIA_INGRESO,
        )

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}
    mock_correo_repo.guardar.assert_called_once()
    correo = mock_correo_repo.guardar.call_args[0][0]
    assert correo.referencia == "quar-ing-001"
    assert correo.banco == "Bancolombia"
    assert correo.procesado is False
    assert "parseo fallido" in correo.error_parseo


def test_egreso_parse_error_cuarentena_y_200(
    mock_ingreso_repo: MagicMock,
    mock_egreso_repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When parser raises ErrorParseoBanco (egreso path), correo_repo.guardar is called
    and the route returns 200."""
    mock_correo_repo = MagicMock()
    mock_notificador = MagicMock()

    client = _make_client(
        mock_ingreso_repo,
        mock_egreso_repo,
        mock_correo_repo,
        mock_notificador,
        monkeypatch,
    )

    from garay.infraestructura.webhook.parser.base import ErrorParseoBanco

    with patch(
        "garay.infraestructura.webhook.rutas.obtener_parser_egreso",
        side_effect=ErrorParseoBanco("egreso fallido"),
    ):
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_BANCOLOMBIA_EGRESO,
        )

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}
    mock_correo_repo.guardar.assert_called_once()
    correo = mock_correo_repo.guardar.call_args[0][0]
    assert correo.referencia == "quar-egr-001"
    assert correo.banco == "Bancolombia"
    assert correo.procesado is False


def test_parse_error_envia_alerta_dev(
    mock_ingreso_repo: MagicMock,
    mock_egreso_repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On parse error, notificador.notificar is called once per dev_telegram_id."""
    mock_correo_repo = MagicMock()
    mock_notificador = MagicMock()

    client = _make_client(
        mock_ingreso_repo,
        mock_egreso_repo,
        mock_correo_repo,
        mock_notificador,
        monkeypatch,
        dev_ids=_DEV_IDS_STR,
    )

    from garay.infraestructura.webhook.parser.base import ErrorParseoBanco

    with patch(
        "garay.infraestructura.webhook.rutas.obtener_parser",
        side_effect=ErrorParseoBanco("parse falló"),
    ):
        client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_BANCOLOMBIA_INGRESO,
        )

    # Two dev IDs → two alert calls to dev users
    dev_calls = [
        call
        for call in mock_notificador.notificar.call_args_list
        if call[0][1] in ("111111111", "222222222")
    ]
    assert len(dev_calls) == 2


def test_parse_error_nunca_alerta_grupo(
    mock_ingreso_repo: MagicMock,
    mock_egreso_repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On parse error, notificador.notificar is NEVER called with grupo_id.

    Owner decision: parse-failure alerts go only to dev IDs, not the group.
    """
    mock_correo_repo = MagicMock()
    mock_notificador = MagicMock()

    client = _make_client(
        mock_ingreso_repo,
        mock_egreso_repo,
        mock_correo_repo,
        mock_notificador,
        monkeypatch,
        dev_ids=_DEV_IDS_STR,
        grupo_id=_GRUPO_ID,
    )

    from garay.infraestructura.webhook.parser.base import ErrorParseoBanco

    with patch(
        "garay.infraestructura.webhook.rutas.obtener_parser",
        side_effect=ErrorParseoBanco("parse falló"),
    ):
        client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_BANCOLOMBIA_INGRESO,
        )

    # The group must NEVER receive a parse-failure alert.
    grupo_calls = [
        c
        for c in mock_notificador.notificar.call_args_list
        if c[0][1] == _GRUPO_ID
    ]
    assert len(grupo_calls) == 0, (
        f"Expected no group alerts on parse failure but got {len(grupo_calls)}: {grupo_calls}"
    )

    # Dev IDs must still be notified (regression guard).
    dev_calls = [
        c
        for c in mock_notificador.notificar.call_args_list
        if c[0][1] in ("111111111", "222222222")
    ]
    assert len(dev_calls) == 2


def test_alerta_falla_no_rompe_200(
    mock_ingreso_repo: MagicMock,
    mock_egreso_repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When notificador.notificar raises NotificadorError, the route still returns 200
    and correo_repo.guardar was already called (persistence is NOT rolled back)."""
    mock_correo_repo = MagicMock()
    mock_notificador = MagicMock()
    mock_notificador.notificar.side_effect = NotificadorError("Telegram down")

    client = _make_client(
        mock_ingreso_repo,
        mock_egreso_repo,
        mock_correo_repo,
        mock_notificador,
        monkeypatch,
    )

    from garay.infraestructura.webhook.parser.base import ErrorParseoBanco

    with patch(
        "garay.infraestructura.webhook.rutas.obtener_parser",
        side_effect=ErrorParseoBanco("parse falló"),
    ):
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_BANCOLOMBIA_INGRESO,
        )

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}
    mock_correo_repo.guardar.assert_called_once()


def test_dev_telegram_ids_vacio_no_alerta(
    mock_ingreso_repo: MagicMock,
    mock_egreso_repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When dev_telegram_ids is empty, no dev alert is sent and no crash occurs."""
    mock_correo_repo = MagicMock()
    mock_notificador = MagicMock()

    client = _make_client(
        mock_ingreso_repo,
        mock_egreso_repo,
        mock_correo_repo,
        mock_notificador,
        monkeypatch,
        dev_ids="",   # empty
        grupo_id="",  # also empty so we only assert dev behaviour
    )

    from garay.infraestructura.webhook.parser.base import ErrorParseoBanco

    with patch(
        "garay.infraestructura.webhook.rutas.obtener_parser",
        side_effect=ErrorParseoBanco("parse falló"),
    ):
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_BANCOLOMBIA_INGRESO,
        )

    assert response.status_code == 200
    mock_notificador.notificar.assert_not_called()


def test_cuarentena_duplicada_no_inserta(
    mock_ingreso_repo: MagicMock,
    mock_egreso_repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When correo_repo.guardar raises IntegrityError (duplicate referencia),
    it is swallowed and the route still returns 200."""
    mock_correo_repo = MagicMock()
    mock_correo_repo.guardar.side_effect = IntegrityError(
        "UNIQUE constraint failed", {}, Exception()
    )
    mock_notificador = MagicMock()

    client = _make_client(
        mock_ingreso_repo,
        mock_egreso_repo,
        mock_correo_repo,
        mock_notificador,
        monkeypatch,
    )

    from garay.infraestructura.webhook.parser.base import ErrorParseoBanco

    with patch(
        "garay.infraestructura.webhook.rutas.obtener_parser",
        side_effect=ErrorParseoBanco("parse falló"),
    ):
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_BANCOLOMBIA_INGRESO,
        )

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}


# ---------------------------------------------------------------------------
# Unit tests for alert builders
# ---------------------------------------------------------------------------


def test_snippet_html_escapado() -> None:
    """A body containing HTML tags must appear escaped in the dev alert."""
    msg = construir_alerta_dev(
        banco="Bancolombia",
        direccion="ingreso",
        referencia="msg-xss-001",
        correo_origen="bank@example.com",
        error_parseo="<script>alert('xss')</script>",
        cuerpo_snippet="<b>Hello</b>",
    )
    assert "<script>" not in msg
    assert "&lt;script&gt;" in msg
    assert "<b>Hello</b>" not in msg
    assert "&lt;b&gt;" in msg


def test_construir_alerta_dev_trunca_snippet() -> None:
    """Snippets longer than 500 chars are truncated before escaping."""
    long_body = "A" * 600
    msg = construir_alerta_dev(
        banco="Nequi",
        direccion="egreso",
        referencia="msg-trunc",
        correo_origen="nequi@nequi.com.co",
        error_parseo="short error",
        cuerpo_snippet=long_body,
    )
    # The raw 600-char string should not appear verbatim
    assert "A" * 501 not in msg
    # But the first 500 'A's should be present (after escaping, they remain 'A')
    assert "A" * 500 in msg


