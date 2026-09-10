"""Shared cosmetic text normalization for user-entered free text.

Deliberately NON-destructive: trims and collapses whitespace and capitalizes the
first letter. It does NOT correct spelling nor change words, so proper names
(hotels, tours, people) are never mangled.
"""

from __future__ import annotations


def normalizar_texto(valor: str) -> str:
    """Quita espacios sobrantes y capitaliza la primera letra. No corrige palabras."""
    limpio = " ".join(valor.split())
    if not limpio:
        return limpio
    return limpio[0].upper() + limpio[1:]
