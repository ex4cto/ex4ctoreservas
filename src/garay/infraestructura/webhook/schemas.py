"""Pydantic schemas for the email webhook endpoint."""

from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel


class PayloadEmail(BaseModel):
    message_id: str
    remitente_email: str
    correo_destinatario: str
    asunto: str
    cuerpo_html: str
    cuerpo_texto: str


class PagoExtraido(BaseModel):
    monto: Decimal
    remitente: str
    banco_origen: str
    fecha_pago: datetime.datetime
