"""Tests for egreso routing in webhook email routes — RED phase."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from tests.infraestructura.webhook.conftest import _SECRET

# FIX 1 RED: Transport payloads whose body DOES contain a transaction signal.
# These must be SILENTLY DROPPED (not quarantined) so correo_repo.guardar is
# never called.  The response must still be 200.
_PAYLOAD_UBER_CON_SENAL_TRANSACCION = {
    "message_id": "egr-uber-100",
    "remitente_email": "noreply@uber.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Resumen de tu viaje con Uber",
    # "recibiste" is in _SENALES_TRANSACCION — forces the old route through
    # es_transaccion=True then obtener_parser_egreso("Uber") → no parser → quarantine
    "cuerpo_html": "",
    "cuerpo_texto": "recibiste un cobro por tu viaje",
}

_PAYLOAD_DIDI_CON_SENAL_TRANSACCION = {
    "message_id": "egr-didi-100",
    "remitente_email": "noreply@co.didiglobal.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Tu viaje DiDi",
    # "compraste" is in _SENALES_TRANSACCION
    "cuerpo_html": "",
    "cuerpo_texto": "compraste un viaje DiDi",
}

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


class TestUberDiDiSilentDrop:
    """FIX 1: Uber/DiDi emails are ALWAYS silently dropped in PR-A.

    Even when the body contains a transaction signal, transport emails must NOT
    reach obtener_parser_egreso (which has no Uber/DiDi parser yet) and must NOT
    be quarantined.  They must return 200 without any repo write.
    """

    def test_uber_con_senal_transaccion_silently_dropped(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
        mock_correo_repo: MagicMock,
    ) -> None:
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_UBER_CON_SENAL_TRANSACCION,
        )
        assert response.status_code == 200
        assert response.json() == {"estado": "ok"}
        mock_egreso_repo.guardar.assert_not_called()
        mock_ingreso_repo.guardar.assert_not_called()
        mock_correo_repo.guardar.assert_not_called()

    def test_didi_con_senal_transaccion_silently_dropped(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
        mock_correo_repo: MagicMock,
    ) -> None:
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_DIDI_CON_SENAL_TRANSACCION,
        )
        assert response.status_code == 200
        assert response.json() == {"estado": "ok"}
        mock_egreso_repo.guardar.assert_not_called()
        mock_ingreso_repo.guardar.assert_not_called()
        mock_correo_repo.guardar.assert_not_called()
