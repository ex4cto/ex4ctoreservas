"""Entidades del modulo liquidaciones — pagos a freelancers."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from garay.dominio.comun.dinero import Dinero


@dataclass(frozen=True)
class PagoReferido:
    """Registro de un pago realizado a un referido (alias externo) por una venta."""

    id: uuid.UUID
    venta_id: uuid.UUID
    referido_alias: str
    monto: Dinero
    fecha_pago: datetime.datetime
    registrado_por_telegram_id: int
    registrado_por_nombre: str | None


@dataclass
class PagoFreelancer:
    """Registro de un pago realizado a un freelancer por sus comisiones en un periodo."""

    id: uuid.UUID
    freelancer_id: uuid.UUID
    monto: Dinero
    desde: datetime.date
    hasta: datetime.date
    fecha_pago: datetime.datetime
    registrado_por_telegram_id: int
    registrado_por_nombre: str | None
