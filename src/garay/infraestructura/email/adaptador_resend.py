"""Resend HTTP API adapter for sending HTML invoices."""

from __future__ import annotations

import httpx

from garay.dominio.puertos.servicios_externos import NotificadorEmail


class ResendAdapter(NotificadorEmail):
    _URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, from_address: str) -> None:
        self._api_key = api_key
        self._from_address = from_address

    def enviar(self, destinatario: str, asunto: str, cuerpo_html: str) -> None:
        response = httpx.post(
            self._URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "from": self._from_address,
                "to": [destinatario],
                "subject": asunto,
                "html": cuerpo_html,
            },
            timeout=10.0,
        )
        response.raise_for_status()
