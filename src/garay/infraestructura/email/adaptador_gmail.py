"""Gmail SMTP adapter for sending HTML invoices."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from garay.dominio.puertos.servicios_externos import NotificadorEmail


class GmailAdapter(NotificadorEmail):
    _HOST = "smtp.gmail.com"
    _PORT = 465

    def __init__(self, usuario: str, app_password: str) -> None:
        self._usuario = usuario
        self._password = app_password

    def enviar(self, destinatario: str, asunto: str, cuerpo_html: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"] = self._usuario
        msg["To"] = destinatario
        msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))
        with smtplib.SMTP_SSL(self._HOST, self._PORT, timeout=10) as server:
            server.login(self._usuario, self._password)
            server.sendmail(self._usuario, destinatario, msg.as_string())
