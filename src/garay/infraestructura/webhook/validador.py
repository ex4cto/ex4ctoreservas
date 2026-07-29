"""Validates the shared secret received in Forward Email webhook requests."""

from __future__ import annotations

import hmac


class ErrorSecretInvalido(Exception):
    """Raised when the provided webhook secret does not match the configured one."""


def validar_secret(secret_recibido: str, *, expected: str) -> None:
    """Compare the received secret against the expected value.

    Uses hmac.compare_digest to prevent timing attacks.
    Raises ErrorSecretInvalido if the secret is wrong or empty.
    """
    if not hmac.compare_digest(secret_recibido, expected):
        raise ErrorSecretInvalido("Secret invalido")
