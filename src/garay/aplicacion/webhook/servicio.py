"""Application service: converts PagoExtraido/EgresoExtraido into domain entities."""

from __future__ import annotations

import datetime
import uuid

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso, Ingreso
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.dominio.puertos.repositorios import EgresoRepository, IngresoRepository
from garay.infraestructura.webhook.schemas import EgresoExtraido, PagoExtraido


def guardar_ingreso(
    pago: PagoExtraido,
    referencia: str,
    repo: IngresoRepository,
    *,
    moneda: str,
    correo_origen: str | None = None,
    reenviado: bool = False,
) -> Ingreso:
    """Convert a PagoExtraido into an Ingreso entity and persist it."""
    ingreso = Ingreso(
        id=uuid.uuid4(),
        banco=pago.banco_origen,
        monto=Dinero(pago.monto, moneda),
        fecha=pago.fecha_pago.date(),
        referencia=referencia,
        remitente=pago.remitente,
        clasificado=False,
        fecha_recibido=datetime.datetime.now(datetime.UTC),
        correo_origen=correo_origen,
        reenviado=reenviado,
    )
    repo.guardar(ingreso)
    return ingreso


def guardar_egreso(
    pago: EgresoExtraido,
    referencia: str,
    repo: EgresoRepository,
    *,
    moneda: str,
    correo_origen: str | None = None,
    reenviado: bool = False,
) -> Egreso:
    """Convert an EgresoExtraido into an Egreso entity and persist it."""
    egreso = Egreso(
        id=uuid.uuid4(),
        descripcion=pago.descripcion,
        monto=Dinero(pago.monto, moneda),
        fecha=pago.fecha_egreso.date(),
        categoria="otro",
        tipo=TipoEgreso.AUTOMATICO,
        referencia=referencia,
        fecha_recibido=datetime.datetime.now(datetime.UTC),
        correo_origen=correo_origen,
        reenviado=reenviado,
    )
    repo.guardar(egreso)
    return egreso
