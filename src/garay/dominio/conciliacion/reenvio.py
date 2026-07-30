"""Domain utility: detect whether an email is a forward."""

from __future__ import annotations

_SUBJECT_PREFIXES = ("fwd:", "fw:", "rv:")
_BODY_MARKERS = ("forwarded message",)


def detectar_reenvio(asunto: str, cuerpo: str) -> bool:
    """Return True if the email appears to be a forwarded message.

    Checks:
    - Subject (case-insensitive) contains any of: "fwd:", "fw:", "rv:"
    - Body (case-insensitive) contains "forwarded message"
    """
    asunto_lower = asunto.lower()
    if any(prefix in asunto_lower for prefix in _SUBJECT_PREFIXES):
        return True

    cuerpo_lower = cuerpo.lower()
    return any(marker in cuerpo_lower for marker in _BODY_MARKERS)
