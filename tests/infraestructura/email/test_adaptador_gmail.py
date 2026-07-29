"""Tests for GmailAdapter — uses mock SMTP to avoid real network calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from garay.infraestructura.email.adaptador_gmail import GmailAdapter


class TestGmailAdapterEnviar:
    def test_enviar_llama_smtp_ssl_con_host_y_puerto_correctos(self) -> None:
        adapter = GmailAdapter(usuario="test@gmail.com", app_password="secret")
        with patch("garay.infraestructura.email.adaptador_gmail.smtplib.SMTP_SSL") as mock_ssl:
            mock_server = MagicMock()
            mock_ssl.return_value.__enter__.return_value = mock_server
            adapter.enviar("dest@example.com", "Asunto", "<html>cuerpo</html>")
        mock_ssl.assert_called_once_with("smtp.gmail.com", 465)

    def test_enviar_hace_login_con_credenciales(self) -> None:
        adapter = GmailAdapter(usuario="user@gmail.com", app_password="apppass")
        with patch("garay.infraestructura.email.adaptador_gmail.smtplib.SMTP_SSL") as mock_ssl:
            mock_server = MagicMock()
            mock_ssl.return_value.__enter__.return_value = mock_server
            adapter.enviar("dest@example.com", "Asunto", "<html>cuerpo</html>")
        mock_server.login.assert_called_once_with("user@gmail.com", "apppass")

    def test_enviar_a_destinatario_correcto(self) -> None:
        adapter = GmailAdapter(usuario="user@gmail.com", app_password="apppass")
        with patch("garay.infraestructura.email.adaptador_gmail.smtplib.SMTP_SSL") as mock_ssl:
            mock_server = MagicMock()
            mock_ssl.return_value.__enter__.return_value = mock_server
            adapter.enviar("cliente@example.com", "Factura", "<html>factura</html>")
        call_args = mock_server.sendmail.call_args
        assert call_args[0][1] == "cliente@example.com"

    def test_enviar_distinto_destinatario_llama_sendmail(self) -> None:
        adapter = GmailAdapter(usuario="user@gmail.com", app_password="apppass")
        with patch("garay.infraestructura.email.adaptador_gmail.smtplib.SMTP_SSL") as mock_ssl:
            mock_server = MagicMock()
            mock_ssl.return_value.__enter__.return_value = mock_server
            adapter.enviar("otro@empresa.com", "Otro asunto", "<p>cuerpo</p>")
        call_args = mock_server.sendmail.call_args
        assert call_args[0][1] == "otro@empresa.com"
