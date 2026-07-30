"""Tests for ResendAdapter."""

from __future__ import annotations

import httpx
import pytest
from unittest.mock import MagicMock, patch

from garay.infraestructura.email.adaptador_resend import ResendAdapter


class TestResendAdapterEnviar:
    def test_post_usa_url_correcta(self) -> None:
        adapter = ResendAdapter(api_key="key123", from_address="noreply@ex4cto.co")
        with patch("garay.infraestructura.email.adaptador_resend.httpx.post") as mock_post:
            mock_post.return_value = MagicMock()
            adapter.enviar("dest@example.com", "Asunto", "<html>cuerpo</html>")
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://api.resend.com/emails"

    def test_post_incluye_authorization_header(self) -> None:
        adapter = ResendAdapter(api_key="mi_clave", from_address="noreply@ex4cto.co")
        with patch("garay.infraestructura.email.adaptador_resend.httpx.post") as mock_post:
            mock_post.return_value = MagicMock()
            adapter.enviar("dest@example.com", "Asunto", "<html>body</html>")
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer mi_clave"

    def test_post_body_tiene_campos_correctos(self) -> None:
        adapter = ResendAdapter(api_key="key", from_address="facturas@ex4cto.co")
        with patch("garay.infraestructura.email.adaptador_resend.httpx.post") as mock_post:
            mock_post.return_value = MagicMock()
            adapter.enviar("cliente@empresa.com", "Factura #1", "<p>html</p>")
        json_body = mock_post.call_args[1]["json"]
        assert json_body["from"] == "facturas@ex4cto.co"
        assert json_body["subject"] == "Factura #1"
        assert json_body["html"] == "<p>html</p>"

    def test_to_es_lista(self) -> None:
        adapter = ResendAdapter(api_key="key", from_address="noreply@ex4cto.co")
        with patch("garay.infraestructura.email.adaptador_resend.httpx.post") as mock_post:
            mock_post.return_value = MagicMock()
            adapter.enviar("solo@example.com", "Asunto", "<p>body</p>")
        json_body = mock_post.call_args[1]["json"]
        assert json_body["to"] == ["solo@example.com"]

    def test_error_http_propaga_excepcion(self) -> None:
        adapter = ResendAdapter(api_key="key_invalida", from_address="noreply@ex4cto.co")
        with patch("garay.infraestructura.email.adaptador_resend.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "422 Unprocessable Entity",
                request=MagicMock(),
                response=MagicMock(),
            )
            mock_post.return_value = mock_response
            with pytest.raises(httpx.HTTPStatusError):
                adapter.enviar("dest@example.com", "Asunto", "<html>body</html>")

    def test_post_usa_timeout_10(self) -> None:
        adapter = ResendAdapter(api_key="key", from_address="noreply@ex4cto.co")
        with patch("garay.infraestructura.email.adaptador_resend.httpx.post") as mock_post:
            mock_post.return_value = MagicMock()
            adapter.enviar("dest@example.com", "Asunto", "<html>body</html>")
        assert mock_post.call_args[1]["timeout"] == 10.0
