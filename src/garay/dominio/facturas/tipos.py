"""Enums del dominio de facturas."""

from __future__ import annotations

from enum import StrEnum


class EstadoEnvioFactura(StrEnum):
    """Estado del envio de una factura al cliente por correo."""

    PENDIENTE = "PENDIENTE"
    ENVIADO = "ENVIADO"
    ERROR = "ERROR"
    SIN_EMAIL = "SIN_EMAIL"
