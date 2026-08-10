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


# ---------------------------------------------------------------------------
# Non-transaction pre-filter gate
# ---------------------------------------------------------------------------

_PAYLOAD_NO_TRANSACCION_BANCOLOMBIA = {
    "message_id": "mkt-001",
    "remitente_email": "alertas@notificacionesbancolombia.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Novedades para tu plata",
    "cuerpo_html": "",
    "cuerpo_texto": (
        "Si todo sube, ¿qué pasa con tu plata? "
        "Haz que crezca con un fondo de inversión."
    ),
}

_PAYLOAD_NO_TRANSACCION_NEQUI = {
    "message_id": "sec-001",
    "remitente_email": "somos@nequi.com.co",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Cuida tu info",
    "cuerpo_html": "",
    "cuerpo_texto": (
        "En temporada de declaración cuida tu info y tu plata. "
        "Repórtalo a correosospechoso@nequi.com"
    ),
}


def test_email_no_transaccion_retorna_200_sin_cuarentena_ni_notificacion(
    client: TestClient,
    mock_ingreso_repo: MagicMock,
    mock_correo_repo: MagicMock,
    mock_notificador: MagicMock,
) -> None:
    """A non-transaction email from a known bank must return 200 OK, not quarantine."""
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_NO_TRANSACCION_BANCOLOMBIA,
    )

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}
    mock_correo_repo.guardar.assert_not_called()
    mock_notificador.notificar.assert_not_called()
    mock_ingreso_repo.guardar.assert_not_called()


def test_email_no_transaccion_nequi_retorna_200_sin_cuarentena(
    client: TestClient,
    mock_ingreso_repo: MagicMock,
    mock_correo_repo: MagicMock,
    mock_notificador: MagicMock,
) -> None:
    """A Nequi security/marketing email must also be silently ignored."""
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_NO_TRANSACCION_NEQUI,
    )

    assert response.status_code == 200
    mock_correo_repo.guardar.assert_not_called()
    mock_notificador.notificar.assert_not_called()
    mock_ingreso_repo.guardar.assert_not_called()


def test_email_transaccion_real_sigue_parseando(
    client: TestClient,
    mock_ingreso_repo: MagicMock,
    mock_correo_repo: MagicMock,
) -> None:
    """Regression: a real transaction body must NOT be blocked by the gate."""
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_BANCOLOMBIA,
    )

    assert response.status_code == 200
    mock_ingreso_repo.guardar.assert_called_once()
    mock_correo_repo.guardar.assert_not_called()


# ---------------------------------------------------------------------------
# PSE end-to-end route test
# ---------------------------------------------------------------------------

# Real PSE egreso body — mirrors _TEXTO_PSE from test_parser_pse_egreso.py.
# Sender is a generic Gmail address; detectar_banco falls back to body
# detection and returns "PSE" because _es_pse fires on "serviciopse" / "cus:".
_TEXTO_PSE_EGRESO = (
    "PSE - Transacción Aprobada ✅ CUS 455692497\n"
    "De: serviciopse@achcolombia.com.co\n"
    "¡Hola, Julio Cesar Garay Manzur!\n"
    " Los siguientes son los datos de tu transacción:\n"
    "Valor: $ 124.200,00\n"
    "Empresa: WOMPI S.A.S\n"
    "Descripción: Sent from PayJoy PaymentOptionsProvidersSDK.\n"
    "Fecha de la transacción: 06/07/2026\n"
    "CUS: 455692497\n"
    "Gracias por utilizar nuestro servicio.\n"
)

_PAYLOAD_PSE_EGRESO = {
    "message_id": "pse-001",
    "remitente_email": "agenciagaraytour1@gmail.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "PSE - Transacción Aprobada",
    "cuerpo_html": "",
    "cuerpo_texto": _TEXTO_PSE_EGRESO,
}


def test_email_pse_egreso_persiste_y_no_cuarentena(
    client: TestClient,
    mock_egreso_repo: MagicMock,
    mock_ingreso_repo: MagicMock,
    mock_correo_repo: MagicMock,
    mock_notificador: MagicMock,
) -> None:
    """A real PSE egreso email must be parsed, persisted, and never quarantined.

    PSE passes the es_transaccion gate via _es_pse body markers (not a verb),
    and detectar_direccion routes it to egreso via the same markers.
    """
    response = client.post(
        f"/webhook/email?secret={_SECRET}",
        json=_PAYLOAD_PSE_EGRESO,
    )

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}
    mock_egreso_repo.guardar.assert_called_once()
    mock_correo_repo.guardar.assert_not_called()
    mock_notificador.notificar.assert_not_called()
