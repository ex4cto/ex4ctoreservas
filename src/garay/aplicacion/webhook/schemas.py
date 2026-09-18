"""Application-layer DTOs for webhook payment extraction."""

from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel


class PagoExtraido(BaseModel):
    monto: Decimal
    remitente: str
    banco_origen: str
    fecha_pago: datetime.datetime


class EgresoExtraido(BaseModel):
    monto: Decimal
    descripcion: str
    banco_origen: str
    fecha_egreso: datetime.datetime
    destinatario: str | None = None
