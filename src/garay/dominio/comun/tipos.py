"""Enums compartidos del dominio Garay."""

from __future__ import annotations

from enum import StrEnum


class TipoCliente(StrEnum):
    INTERNO = "INTERNO"
    EXTERNO = "EXTERNO"
    DIGITAL = "DIGITAL"


class EstadoVenta(StrEnum):
    PENDIENTE = "PENDIENTE"
    PROCESADA = "PROCESADA"
    CANCELADA = "CANCELADA"
