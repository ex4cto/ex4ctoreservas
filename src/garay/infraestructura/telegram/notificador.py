"""Concrete adapter: NotificadorGrupo backed by the Telegram Bot API."""

from __future__ import annotations

import contextlib
import json
import logging
import urllib.error
import urllib.request

from garay.dominio.puertos.servicios_externos import NotificadorGrupo
from garay.infraestructura.telegram.errores import NotificadorError, NotificadorNoDisponible

_API_BASE = "https://api.telegram.org"

logger = logging.getLogger(__name__)


def _extraer_migrate_id(exc: urllib.error.HTTPError) -> int | None:
    """Return migrate_to_chat_id from a 400 body (group→supergroup), else None."""
    if exc.code != 400:
        return None
    try:
        data = json.loads(exc.read().decode("utf-8"))
    except Exception:
        return None
    mig = (data.get("parameters") or {}).get("migrate_to_chat_id")
    return mig if isinstance(mig, int) else None


class NotificadorGrupoTelegram(NotificadorGrupo):
    """Sends messages to a Telegram group via the Bot API.

    Self-heals a group→supergroup migration: when a send fails with HTTP 400 and
    ``migrate_to_chat_id``, it remembers the new id (in-memory, for this process),
    alerts the devs so they can persist it in ``GARAY_GRUPO_ID``, and retries to
    the new id so the notification still lands.

    Returns the ``message_id`` of the sent message as an ``int`` on success, or
    ``None`` when the notification could not be delivered (exception swallowed by
    the caller's best-effort contract).
    """

    def __init__(self, token: str, dev_ids: list[int] | None = None) -> None:
        self._token = token
        self._dev_ids = list(dev_ids or [])
        # old chat_id -> new supergroup id, learned at runtime.
        self._migraciones: dict[str, str] = {}

    def notificar(self, mensaje: str, grupo_id: str) -> int | None:
        destino = self._migraciones.get(grupo_id, grupo_id)
        migrate_id, message_id = self._enviar(destino, mensaje)
        if migrate_id is None:
            return message_id
        # El grupo migró a supergrupo: recordar, alertar y reintentar al id nuevo.
        nuevo = migrate_id
        self._migraciones[grupo_id] = nuevo
        logger.warning("Grupo de notificaciones migró a supergrupo: %s -> %s", grupo_id, nuevo)
        self._alertar_migracion(grupo_id, nuevo)
        # Retry to new supergroup id; a second migration (rare) is ignored.
        _, message_id = self._enviar(nuevo, mensaje)
        return message_id

    def _enviar(self, chat_id: str, mensaje: str) -> tuple[str | None, int | None]:
        """Send one message.

        Returns a tuple ``(migrate_id, message_id)`` where:
        - ``migrate_id`` is the new supergroup id as a string if the chat migrated, else ``None``.
        - ``message_id`` is the Telegram ``message_id`` integer from the API response on success,
          or ``None`` when the response could not be parsed.

        Raises NotificadorError / NotificadorNoDisponible on other failures.
        """
        url = f"{_API_BASE}/bot{self._token}/sendMessage"
        payload = json.dumps(
            {"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read()
            try:
                data = json.loads(body.decode("utf-8"))
                raw_id = (data.get("result") or {}).get("message_id")
                msg_id = int(raw_id) if isinstance(raw_id, (int, float)) else None
            except Exception:
                msg_id = None
            return None, msg_id
        except urllib.error.HTTPError as exc:
            nuevo = _extraer_migrate_id(exc)
            if nuevo is not None:
                return str(nuevo), None
            raise NotificadorError(f"Telegram API returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise NotificadorNoDisponible(f"Telegram API is unreachable: {exc.reason}") from exc
        except Exception as exc:
            # Honor the port contract: no unexpected error (malformed URL -> ValueError,
            # platform OSError, etc.) may escape raw, or callers relying on the
            # NotificadorError/NotificadorNoDisponible contract would break.
            raise NotificadorNoDisponible(f"Telegram notification failed: {exc}") from exc

    def _alertar_migracion(self, viejo: str, nuevo: str) -> None:
        """Best-effort DM to devs so they persist the new id in GARAY_GRUPO_ID."""
        texto = (
            "⚠️ El grupo de notificaciones migró a supergrupo.\n"
            f"Nuevo ID: {nuevo} (antes {viejo}).\n"
            "Actualiza GARAY_GRUPO_ID en Railway para que el cambio sea permanente."
        )
        for dev in self._dev_ids:
            with contextlib.suppress(Exception):
                self._enviar(str(dev), texto)
