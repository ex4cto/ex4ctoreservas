"""Shared date helpers for the application layer."""

from __future__ import annotations

import datetime


def parsear_fecha(texto: str) -> datetime.datetime | None:
    """Parse a user-supplied date string.

    Accepted formats (in order of precedence):
    - ``DD/MM/YYYY HH:MM``
    - ``DD/MM/YYYY``
    - ``DD/MM/YY``
    - ``DD/MM`` (year defaults to the current year)

    Returns ``None`` when the text does not match any accepted format.
    """
    texto = texto.strip()
    now = datetime.datetime.now()
    formatos_con_año = ["%d/%m/%Y %H:%M", "%d/%m/%Y", "%d/%m/%y"]
    for fmt in formatos_con_año:
        try:
            return datetime.datetime.strptime(texto, fmt)
        except ValueError:
            continue
    try:
        return datetime.datetime.strptime(f"{texto}/{now.year}", "%d/%m/%Y")
    except ValueError:
        pass
    return None


def formatear_fechas_compactas(
    pares: list[tuple[str, datetime.datetime]],
) -> str:
    """Render ordered (tour name, datetime) pairs as a compact inline string.

    Each pair becomes ``"{nombre} DD/MM HH:MM"``; pairs are joined by ``", "``
    in the supplied order. Returns an empty string when there are no pairs.
    """
    return ", ".join(
        f"{nombre} {dt.strftime('%d/%m %H:%M')}" for nombre, dt in pares
    )
