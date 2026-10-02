"""urllib-based adapter: EnviadorFotoPort backed by the Telegram Bot API sendPhoto.

Uses multipart/form-data so it works in BOTH the PTB async event loop (via
run_in_executor) AND standalone scripts (asyncio.run), with no PTB Bot instance.
Handles the group→supergroup migration self-heal pattern from notificador.py.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart

from garay.dominio.puertos.servicios_externos import EnviadorFotoPort

_API_BASE = "https://api.telegram.org"
_BOUNDARY = "GarayToursPhotoUpload"

logger = logging.getLogger(__name__)


def _build_multipart(fields: dict[str, str], file_field: str, file_bytes: bytes) -> bytes:
    """Build raw multipart/form-data body.

    Args:
        fields: string key-value fields (e.g. {"chat_id": "-100..."}).
        file_field: name of the file field (e.g. "photo").
        file_bytes: raw PNG bytes.

    Returns:
        Raw bytes body for the multipart POST.
    """
    body = io.BytesIO()
    sep = f"--{_BOUNDARY}\r\n".encode()
    end = f"--{_BOUNDARY}--\r\n".encode()

    for name, value in fields.items():
        body.write(sep)
        body.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.write(value.encode())
        body.write(b"\r\n")

    # File part
    body.write(sep)
    body.write(
        f'Content-Disposition: form-data; name="{file_field}"; filename="lista_precios.png"\r\n'.encode()
    )
    body.write(b"Content-Type: image/png\r\n\r\n")
    body.write(file_bytes)
    body.write(b"\r\n")
    body.write(end)

    return body.getvalue()


def _extraer_migrate_id(body: bytes) -> int | None:
    """Parse a Telegram error body and return migrate_to_chat_id if present."""
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        return None
    mig = (data.get("parameters") or {}).get("migrate_to_chat_id")
    return mig if isinstance(mig, int) else None


def _sync_send(token: str, imagen: bytes, grupo_id: str) -> None:
    """Synchronous urllib POST to sendPhoto.

    Handles supergroup migration: on 400 with migrate_to_chat_id, retries once
    with the new chat_id.

    Raises:
        RuntimeError: On non-migration Telegram errors.
        urllib.error.URLError: On network errors.
    """
    url = f"{_API_BASE}/bot{token}/sendPhoto"

    def _post(chat_id: str) -> bytes:
        body = _build_multipart({"chat_id": chat_id}, "photo", imagen)
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={_BOUNDARY}"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return resp.read()  # type: ignore[no-any-return]

    try:
        _post(grupo_id)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        migrate_id = _extraer_migrate_id(raw)
        if migrate_id is not None:
            logger.warning(
                "EnviadorFotoTelegram: group migrated to supergroup %s, retrying",
                migrate_id,
            )
            try:
                _post(str(migrate_id))
            except urllib.error.HTTPError as retry_exc:
                raise RuntimeError(
                    f"Telegram sendPhoto failed after migration retry: HTTP {retry_exc.code}"
                ) from retry_exc
        else:
            raise RuntimeError(
                f"Telegram sendPhoto HTTP {exc.code}: {raw[:200]!r}"
            ) from exc


class EnviadorFotoTelegram(EnviadorFotoPort):
    """Sends PNG bytes to a Telegram group via the Bot API sendPhoto endpoint.

    Works from both the PTB event loop (async context) and standalone scripts
    (asyncio.run), because it offloads the blocking urllib call to the default
    thread pool via run_in_executor.

    Args:
        token: Telegram bot token (e.g. "123456:ABC-xyz").
    """

    def __init__(self, token: str) -> None:
        self._token = token

    async def enviar(self, imagen: bytes, grupo_id: str) -> None:
        """Send *imagen* (PNG bytes) to *grupo_id* via sendPhoto.

        Uses asyncio's default executor to keep the event loop non-blocking.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_send, self._token, imagen, grupo_id)
