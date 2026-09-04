"""Normalización y validación de correos electrónicos (dominio compartido)."""

from __future__ import annotations

import re

_PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalizar_email(texto: str) -> str:
    """Quita TODOS los espacios y pasa a minúsculas.

    Corrige errores de captura comunes: 'Anais. Vignon. 5@Gmail.com' ->
    'anais.vignon.5@gmail.com'. No corrige errores de ortografía humanos.
    """
    return re.sub(r"\s+", "", texto).lower()


def es_email_valido(texto: str) -> bool:
    """True si ``texto`` tiene forma ``local@dominio.tld`` (sin espacios)."""
    return bool(_PATRON_EMAIL.match(texto))
