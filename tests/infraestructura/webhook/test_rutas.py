"""Tests for webhook email routes — TDD RED phase.

Uses FastAPI TestClient with an in-memory SQLite DB.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from garay.aplicacion.webhook.app import crear_app

_SECRET = "test-secret-12345"

_PAYLOAD_BANCOLOMBIA = {
    "message_id": "msg-001",
    "remitente_email": "alertas@notificacionesbancolombia.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Transferencia recibida",
    "cuerpo_html": "",
    "cuerpo_texto": (
        "recibiste una transferencia de Carlos Gomez por $500,000 "
        "el 15/07/26 a las 10:30"
    ),
}

_PAYLOAD_BANCO_DESCONOCIDO = {
    "message_id": "msg-002",
    "remitente_email": "alerts@daviplata.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Pago recibido",
    "cuerpo_html": "",
    "cuerpo_texto": "Recibiste un pago de 100,000",
}


@pytest.fixture()
def mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.existe_referencia.return_value = False
    return repo


@pytest.fixture()
def client(
    mock_repo: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("GARAY_FORWARD_EMAIL_SECRET", _SECRET)
    monkeypatch.setenv("GARAY_MONEDA_PREDETERMINADA", "COP")
    # Clear lru_cache so settings re-read from env during the test.
    import garay.config.settings as _settings_mod

    _settings_mod.obtener_settings.cache_clear()
    app = crear_app(repo=mock_repo)
    yield TestClient(app)
    _settings_mod.obtener_settings.cache_clear()


def test_payload_bancolombia_valido_retorna_ok(client: TestClient, mock_repo: MagicMock) -> None:
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_BANCOLOMBIA,
    )

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}
    mock_repo.guardar.assert_called_once()


def test_secret_invalido_retorna_403(client: TestClient, mock_repo: MagicMock) -> None:
    response = client.post(
        "/webhook/email?secret=wrong-secret",
        json=_PAYLOAD_BANCOLOMBIA,
    )

    assert response.status_code == 403
    mock_repo.guardar.assert_not_called()


def test_message_id_duplicado_no_guarda(client: TestClient, mock_repo: MagicMock) -> None:
    mock_repo.existe_referencia.return_value = True

    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_BANCOLOMBIA,
    )

    assert response.status_code == 200
    mock_repo.guardar.assert_not_called()


def test_banco_desconocido_retorna_ok_sin_guardar(
    client: TestClient, mock_repo: MagicMock
) -> None:
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_BANCO_DESCONOCIDO,
    )

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}
    mock_repo.guardar.assert_not_called()


def test_message_id_vacio_retorna_ok_sin_guardar(
    client: TestClient, mock_repo: MagicMock
) -> None:
    payload = {**_PAYLOAD_BANCOLOMBIA, "message_id": ""}
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=payload,
    )

    assert response.status_code == 200
    mock_repo.guardar.assert_not_called()
