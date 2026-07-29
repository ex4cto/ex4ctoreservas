"""Tests for egreso routing in webhook email routes — RED phase."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from tests.infraestructura.webhook.conftest import _SECRET

_PAYLOAD_BANCOLOMBIA_EGRESO = {
    "message_id": "egr-001",
    "remitente_email": "alertas@notificacionesbancolombia.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Compra realizada",
    "cuerpo_html": "",
    "cuerpo_texto": (
        "Bancolombia: Compraste $69.328,00 en MOVISTAR PAGOSEPAYCO con tu T.Deb *9283, "
        "el 27/07/2026 a las 18:25."
    ),
}

_PAYLOAD_NEQUI_EGRESO = {
    "message_id": "egr-002",
    "remitente_email": "somos@nequi.com.co",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Enviaste dinero",
    "cuerpo_html": "",
    "cuerpo_texto": (
        "Enviaste de manera exitosa 5.000 a la llave 1047487553 de BRYAN CASTRO "
        "el 25 de julio de 2026 a las 7:05 p.m."
    ),
}

_PAYLOAD_BANCO_DESCONOCIDO = {
    "message_id": "egr-003",
    "remitente_email": "alerts@daviplata.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Egreso",
    "cuerpo_html": "",
    "cuerpo_texto": "Compraste algo en algun lugar",
}


def test_email_egreso_bancolombia_llama_egreso_repo(
    client: TestClient, mock_egreso_repo: MagicMock, mock_ingreso_repo: MagicMock
) -> None:
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_BANCOLOMBIA_EGRESO,
    )
    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}
    mock_egreso_repo.guardar.assert_called_once()
    mock_ingreso_repo.guardar.assert_not_called()


def test_email_egreso_nequi_llama_egreso_repo(
    client: TestClient, mock_egreso_repo: MagicMock, mock_ingreso_repo: MagicMock
) -> None:
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_NEQUI_EGRESO,
    )
    assert response.status_code == 200
    mock_egreso_repo.guardar.assert_called_once()
    mock_ingreso_repo.guardar.assert_not_called()


def test_banco_desconocido_no_guarda_nada(
    client: TestClient, mock_egreso_repo: MagicMock, mock_ingreso_repo: MagicMock
) -> None:
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_BANCO_DESCONOCIDO,
    )
    assert response.status_code == 200
    mock_egreso_repo.guardar.assert_not_called()
    mock_ingreso_repo.guardar.assert_not_called()
