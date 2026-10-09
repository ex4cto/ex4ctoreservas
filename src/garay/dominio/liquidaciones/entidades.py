"""Entidades del modulo liquidaciones — pagos a freelancers."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from garay.dominio.comun.dinero import Dinero


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
