"""Commands for the ventas application module."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from garay.dominio.clientes.entidades import CampoCliente
from garay.dominio.comun.tipos import TipoCliente


@dataclass(frozen=True)
class AnularVentaComando:
    venta_id: uuid.UUID
    motivo: str
    realizada_por_telegram_id: int
    realizada_por_nombre: str | None


@dataclass(frozen=True)
class EditarFechaVentaComando:
    venta_id: uuid.UUID
    nueva_fecha: datetime.datetime
    motivo: str
    realizada_por_telegram_id: int
    realizada_por_nombre: str | None


@dataclass(frozen=True)
class EditarClienteVentaComando:
    venta_id: uuid.UUID
    campo: CampoCliente
    nuevo_valor: str
    motivo: str
    realizada_por_telegram_id: int
    realizada_por_nombre: str | None


@dataclass(frozen=True)
class EditarCanalVentaComando:
    venta_id: uuid.UUID
    nuevo_tipo: TipoCliente
    punto_id: uuid.UUID | None
    motivo: str
    realizada_por_telegram_id: int
    realizada_por_nombre: str | None
