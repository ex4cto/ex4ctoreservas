"""Application service: converts PagoExtraido into Ingreso and persists it."""

from __future__ import annotations

import uuid

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Ingreso
from garay.dominio.puertos.repositorios import IngresoRepository
from garay.infraestructura.webhook.schemas import PagoExtraido


def guardar_ingreso(
    pago: PagoExtraido,
    referencia: str,
    repo: IngresoRepository,
    *,
    moneda: str = "COP",
) -> Ingreso:
    """Convert a PagoExtraido into an Ingreso entity and persist it.

    Args:
        pago: Structured payment data extracted from a bank email.
        referencia: Unique message ID from Forward Email (used as idempotency key).
        repo: IngresoRepository port implementation.
        moneda: ISO currency code (defaults to COP).

    Returns:
        The persisted Ingreso entity.
    """
    ingreso = Ingreso(
        id=uuid.uuid4(),
        banco=pago.banco_origen,
        monto=Dinero(pago.monto, moneda),
        fecha=pago.fecha_pago.date(),
        referencia=referencia,
        remitente=pago.remitente,
        clasificado=False,
    )
    repo.guardar(ingreso)
    return ingreso
