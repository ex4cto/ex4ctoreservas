"""Concrete adapter: NotificadorGrupo backed by the Telegram Bot API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from garay.dominio.puertos.servicios_externos import NotificadorGrupo
from garay.infraestructura.telegram.errores import NotificadorError, NotificadorNoDisponible

_API_BASE = "https://api.telegram.org"


class NotificadorGrupoTelegram(NotificadorGrupo):
    """Sends messages to a Telegram group via the Bot API."""

    def __init__(self, token: str) -> None:
        self._token = token

    def notificar(self, mensaje: str, grupo_id: str) -> None:
        url = f"{_API_BASE}/bot{self._token}/sendMessage"
        payload = json.dumps(
            {
                "chat_id": grupo_id,
                "text": mensaje,
                "parse_mode": "HTML",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            raise NotificadorError(
                f"Telegram API returned HTTP {exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise NotificadorNoDisponible(
                f"Telegram API is unreachable: {exc.reason}"
            ) from exc
