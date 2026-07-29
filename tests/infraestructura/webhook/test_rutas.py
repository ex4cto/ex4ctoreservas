"""Tests for webhook email routes — TDD RED phase.

Uses FastAPI TestClient with an in-memory SQLite DB.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from tests.infraestructura.webhook.conftest import _SECRET

_PAYLOAD_BANCOLOMBIA = {
    "message_id": "msg-001",
    "remitente_email": "alertas@notificacionesbancolombia.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Transferencia recibida",
    "cuerpo_html": "",
    "cuerpo_texto": (
        "Recibiste una transferencia por $500,000 de Carlos Gomez "
        "en tu cuenta **5643, el 15/07/26 a las 10:30"
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


def test_payload_bancolombia_valido_retorna_ok(
    client: TestClient, mock_ingreso_repo: MagicMock
) -> None:
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_BANCOLOMBIA,
    )

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}
    mock_ingreso_repo.guardar.assert_called_once()


def test_secret_invalido_retorna_403(
    client: TestClient, mock_ingreso_repo: MagicMock
) -> None:
    response = client.post(
        "/webhook/email?secret=wrong-secret",
        json=_PAYLOAD_BANCOLOMBIA,
    )

    assert response.status_code == 403
    mock_ingreso_repo.guardar.assert_not_called()


def test_message_id_duplicado_no_guarda(
    client: TestClient, mock_ingreso_repo: MagicMock
) -> None:
    mock_ingreso_repo.existe_referencia.return_value = True

    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_BANCOLOMBIA,
    )

    assert response.status_code == 200
    mock_ingreso_repo.guardar.assert_not_called()


def test_banco_desconocido_retorna_ok_sin_guardar(
    client: TestClient, mock_ingreso_repo: MagicMock
) -> None:
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_BANCO_DESCONOCIDO,
    )

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}
    mock_ingreso_repo.guardar.assert_not_called()


def test_message_id_vacio_retorna_ok_sin_guardar(
    client: TestClient, mock_ingreso_repo: MagicMock
) -> None:
    payload = {**_PAYLOAD_BANCOLOMBIA, "message_id": ""}
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=payload,
    )

    assert response.status_code == 200
    mock_ingreso_repo.guardar.assert_not_called()
