"""Shared date-formatting helpers for the application layer."""

from __future__ import annotations

import datetime


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
