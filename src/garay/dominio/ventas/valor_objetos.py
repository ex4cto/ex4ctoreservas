"""Value objects del modulo ventas."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Participantes:
    """Agrupa los actores comerciales involucrados en una venta."""

    vendedor_nombre: str | None = None
    cerrador_nombre: str | None = None
    punto_de_venta_id: uuid.UUID | None = None
    referido_nombre: str | None = None
