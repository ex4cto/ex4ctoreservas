"""Commands for the ventas application module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class AnularVentaComando:
    venta_id: uuid.UUID
    motivo: str
    realizada_por_telegram_id: int
    realizada_por_nombre: str | None
