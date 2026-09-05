"""Pure validation and derivation functions for the freelancer domain."""

from __future__ import annotations

import re

from garay.dominio.freelancers.errores import CedulaInvalida, EmailInvalido

_PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_email(texto: str) -> str:
    """Validate and normalize an email address.

    Returns the stripped email on success. Raises EmailInvalido on a value that
    is not a plausible ``local@dominio.tld`` (no spaces, one @, a dotted domain).
    """
    t = texto.strip()
    if not _PATRON_EMAIL.match(t):
        raise EmailInvalido(f"Correo invalido: '{texto!r}'.")
    return t


def validar_cedula(texto: str) -> str:
    """Validate and normalize a Colombian cedula number.

    Args:
        texto: Raw cedula string, possibly with surrounding whitespace.

    Returns:
        Normalized (stripped) cedula string on success.

    Raises:
        CedulaInvalida: If the value is not 6-10 ASCII digits after stripping.
    """
    t = texto.strip()
    if not t.isdigit() or not (6 <= len(t) <= 10):
        raise CedulaInvalida(
            f"Cedula invalida: se esperan entre 6 y 10 digitos, se recibio '{texto!r}'."
        )
    return t


def derivar_display(nombre_completo: str) -> str:
    """Derive a short display name from a full name.

    Rules:
    - Empty string (after splitting) → return ""
    - Single token → return the token verbatim
    - Multiple tokens → "<first token> <initial of second token>."
      (second token = first surname in Latino naming, e.g. "Bryan Castro Gomez" → "Bryan C.")

    Examples:
        "Bryan Castro"        → "Bryan C."
        "Yolymar Perez Banquez" → "Yolymar P."
        "Madonna"             → "Madonna"
        ""                    → ""

    Args:
        nombre_completo: Full name string; leading/trailing whitespace is ignored.

    Returns:
        Derived display string.
    """
    partes = nombre_completo.split()
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    return f"{partes[0]} {partes[1][0]}."
