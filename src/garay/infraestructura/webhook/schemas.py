"""Pydantic schemas for the email webhook endpoint."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, model_validator


class PayloadEmail(BaseModel):
    message_id: str
    remitente_email: str
    correo_destinatario: str
    asunto: str
    cuerpo_html: str
    cuerpo_texto: str

    @model_validator(mode="before")
    @classmethod
    def _normalizar_forward_email(cls, data: Any) -> Any:
        """Accept both our internal flat format and Forward Email's nested format."""
        if not isinstance(data, dict) or "message_id" in data:
            return data

        from_field = data.get("from") or {}
        from_values = from_field.get("value") or []
        remitente = from_values[0].get("address", "") if from_values else ""

        to_field = data.get("to") or {}
        to_values = to_field.get("value") or []
        destinatario = to_values[0].get("address", "") if to_values else ""

        return {
            "message_id": data.get("messageId", ""),
            "remitente_email": remitente,
            "correo_destinatario": destinatario,
            "asunto": data.get("subject", ""),
            "cuerpo_html": data.get("html") or "",
            "cuerpo_texto": data.get("text") or "",
        }


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
