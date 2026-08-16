"""Tests for egreso routing in webhook email routes."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from tests.infraestructura.webhook.conftest import _SECRET

# ---------------------------------------------------------------------------
# Payload fixtures
# ---------------------------------------------------------------------------

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

# Real Uber receipt body — no transaction-signal words, just real receipt content.
_CUERPO_UBER = (
    "Tu viaje con Uber\n"
    "Uber Priority\n"
    "07/08/2026\n"
    "Tarifa base  COP 9,000\n"
    "Propina  COP 1,700\n"
    "Total  COP 10,700\n"
    "Gracias por viajar con Uber."
)

_PAYLOAD_UBER_RECIBO = {
    "message_id": "egr-uber-real-001",
    "remitente_email": "noreply@uber.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Tu viaje con Uber",
    "cuerpo_html": "",
    "cuerpo_texto": _CUERPO_UBER,
}

# Real DiDi receipt body
_CUERPO_DIDI = (
    "Tu viaje DiDi\n"
    "DiDi Express\n"
    "vie, 31 jul, 2026\n"
    "Tarifa base  $11.500\n"
    "Propina  $1.300\n"
    "Total  $12.800\n"
    "Gracias por viajar con DiDi."
)

_PAYLOAD_DIDI_RECIBO = {
    "message_id": "egr-didi-real-001",
    "remitente_email": "didi@co.didiglobal.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Tu viaje DiDi",
    "cuerpo_html": "",
    "cuerpo_texto": _CUERPO_DIDI,
}

# Anti-false-positive: unrelated domain with "uber" in the body text.
_PAYLOAD_FALSE_POSITIVE = {
    "message_id": "egr-fp-001",
    "remitente_email": "marketing@somecompany.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Promo con uber y didi",
    "cuerpo_html": "",
    "cuerpo_texto": (
        "Nos aliamos con uber y didi para ofrecerte descuentos especiales."
    ),
}


# ---------------------------------------------------------------------------
# Existing egreso tests (unchanged behavior)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# PR-B: Real parsing — transport bypass (converts the PR-A silent drop)
# ---------------------------------------------------------------------------


class TestTransporteBypass:
    """PR-B: Uber/DiDi receipt emails are NOW parsed and persisted as egresos.

    The PR-A silent drop guard has been converted into a real bypass:
    - es_transaccion is skipped
    - direccion is forced to EGRESO
    - parser is called; egreso is persisted with categoria='transporte'
    - no ingreso is ever written
    """

    def test_uber_recibo_persiste_egreso(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
        mock_correo_repo: MagicMock,
    ) -> None:
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_UBER_RECIBO,
        )
        assert response.status_code == 200
        assert response.json() == {"estado": "ok"}
        mock_egreso_repo.guardar.assert_called_once()
        mock_ingreso_repo.guardar.assert_not_called()

    def test_uber_recibo_categoria_transporte(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
    ) -> None:
        client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_UBER_RECIBO,
        )
        mock_egreso_repo.guardar.assert_called_once()
        egreso_guardado = mock_egreso_repo.guardar.call_args[0][0]
        assert egreso_guardado.categoria == "transporte"

    def test_didi_recibo_persiste_egreso(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
        mock_correo_repo: MagicMock,
    ) -> None:
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_DIDI_RECIBO,
        )
        assert response.status_code == 200
        mock_egreso_repo.guardar.assert_called_once()
        mock_ingreso_repo.guardar.assert_not_called()

    def test_didi_recibo_categoria_transporte(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
    ) -> None:
        client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_DIDI_RECIBO,
        )
        mock_egreso_repo.guardar.assert_called_once()
        egreso_guardado = mock_egreso_repo.guardar.call_args[0][0]
        assert egreso_guardado.categoria == "transporte"

    def test_falso_positivo_dominio_desconocido_con_palabra_uber(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
        mock_correo_repo: MagicMock,
    ) -> None:
        """Unrelated sender domain with 'uber' in body must NOT trigger transport parsing."""
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_FALSE_POSITIVE,
        )
        assert response.status_code == 200
        # Domain is unknown → banco is None → route drops silently
        mock_egreso_repo.guardar.assert_not_called()
        mock_ingreso_repo.guardar.assert_not_called()
        mock_correo_repo.guardar.assert_not_called()

    def test_uber_idempotencia_message_id_duplicado(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
    ) -> None:
        """Same Uber message_id delivered twice must persist the egreso only once."""
        # First delivery: referencia does not exist
        mock_egreso_repo.existe_referencia.return_value = False
        client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_UBER_RECIBO,
        )
        assert mock_egreso_repo.guardar.call_count == 1

        # Second delivery: referencia now exists → dedup
        mock_egreso_repo.existe_referencia.return_value = True
        client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_UBER_RECIBO,
        )
        # guardar must not have been called a second time
        assert mock_egreso_repo.guardar.call_count == 1

    # FIX 4 — DiDi idempotency (mirrors the Uber one above)
    def test_didi_idempotencia_message_id_duplicado(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
    ) -> None:
        """Same DiDi message_id delivered twice must persist the egreso only once."""
        mock_egreso_repo.existe_referencia.return_value = False
        client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_DIDI_RECIBO,
        )
        assert mock_egreso_repo.guardar.call_count == 1

        mock_egreso_repo.existe_referencia.return_value = True
        client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_DIDI_RECIBO,
        )
        assert mock_egreso_repo.guardar.call_count == 1

    # FIX 5 — assert guardar called before reading call_args (Uber)
    def test_uber_recibo_monto_guardado(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
    ) -> None:
        """guardar must be called and the persisted Egreso carries the parsed monto."""
        client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_UBER_RECIBO,
        )
        mock_egreso_repo.guardar.assert_called_once()
        egreso_guardado = mock_egreso_repo.guardar.call_args[0][0]
        # monto is stored as Dinero; compare via its .monto Decimal attribute
        from decimal import Decimal

        assert egreso_guardado.monto.monto == Decimal("10700.00")

    # FIX 5 — assert guardar called before reading call_args (DiDi)
    def test_didi_recibo_monto_guardado(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
    ) -> None:
        """guardar must be called and the persisted Egreso carries the parsed monto."""
        client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_DIDI_RECIBO,
        )
        mock_egreso_repo.guardar.assert_called_once()
        egreso_guardado = mock_egreso_repo.guardar.call_args[0][0]
        from decimal import Decimal

        assert egreso_guardado.monto.monto == Decimal("12800.00")


# ---------------------------------------------------------------------------
# FIX 3 — Quarantine integration: malformed transport body -> correo_repo fires
# ---------------------------------------------------------------------------

# Uber payload with a body that is detected as transport bank but unparseable
# (no Total line, no date — guaranteed to raise ErrorParseoBanco in the parser)
_PAYLOAD_UBER_MALFORMADO = {
    "message_id": "egr-uber-mal-001",
    "remitente_email": "noreply@uber.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Tu viaje con Uber",
    "cuerpo_html": "",
    "cuerpo_texto": "Hola, gracias por usar Uber. Sin datos de monto.",
}

# DiDi payload with a body that is detected as transport bank but unparseable
_PAYLOAD_DIDI_MALFORMADO = {
    "message_id": "egr-didi-mal-001",
    "remitente_email": "didi@co.didiglobal.com",
    "correo_destinatario": "pagos@garaytours.com",
    "asunto": "Tu viaje DiDi",
    "cuerpo_html": "",
    "cuerpo_texto": "Hola, gracias por usar DiDi. Sin datos de monto.",
}


class TestCuarentenaTransporte:
    """FIX 3: A transport bank email with an unparseable body must be quarantined."""

    def test_uber_malformado_cuarentena(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
        mock_correo_repo: MagicMock,
    ) -> None:
        """Uber detected but unparseable → quarantine fires, no egreso/ingreso persisted."""
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_UBER_MALFORMADO,
        )
        assert response.status_code == 200
        mock_correo_repo.guardar.assert_called_once()
        mock_egreso_repo.guardar.assert_not_called()
        mock_ingreso_repo.guardar.assert_not_called()

    def test_didi_malformado_cuarentena(
        self,
        client: TestClient,
        mock_egreso_repo: MagicMock,
        mock_ingreso_repo: MagicMock,
        mock_correo_repo: MagicMock,
    ) -> None:
        """DiDi detected but unparseable → quarantine fires, no egreso/ingreso persisted."""
        response = client.post(
            f"/webhook/email?secret={_SECRET}",
            json=_PAYLOAD_DIDI_MALFORMADO,
        )
        assert response.status_code == 200
        mock_correo_repo.guardar.assert_called_once()
        mock_egreso_repo.guardar.assert_not_called()
        mock_ingreso_repo.guardar.assert_not_called()
