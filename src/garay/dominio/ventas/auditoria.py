"""Audit domain entity and action enum for the ventas module."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AccionAuditoria(StrEnum):
    EDITAR_FECHA = "EDITAR_FECHA"
    EDITAR_CLIENTE = "EDITAR_CLIENTE"
    ANULAR = "ANULAR"
    EDITAR_CANAL = "EDITAR_CANAL"
    EDITAR_PARTICIPANTES = "EDITAR_PARTICIPANTES"


@dataclass(frozen=True)
class AuditoriaVenta:
    """Immutable audit record for a change performed on a Venta."""

    id: uuid.UUID
    venta_id: uuid.UUID
    accion: AccionAuditoria
    motivo: str
    realizada_por_telegram_id: int
    realizada_por_nombre: str | None
    realizada_at: datetime.datetime
    datos_previos: dict[str, Any] | None = field(default=None)
