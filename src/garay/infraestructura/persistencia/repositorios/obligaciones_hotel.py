"""SQLAlchemy implementation of ObligacionHotelRepository."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import ObligacionHotel
from garay.dominio.puertos.repositorios import ObligacionHotelRepository
from garay.infraestructura.persistencia.modelos import ObligacionHotelModel


def _to_orm(o: ObligacionHotel) -> ObligacionHotelModel:
    return ObligacionHotelModel(
        id=o.id,
        punto_de_venta_nombre=o.punto_de_venta_nombre,
        receptor_nombre=o.receptor_nombre,
        monto_cuota_dia_1=Decimal(str(o.monto_cuota_dia_1)),
        monto_cuota_dia_2=(
            Decimal(str(o.monto_cuota_dia_2)) if o.monto_cuota_dia_2 is not None else None
        ),
        dia_pago_1=o.dia_pago_1,
        dia_pago_2=o.dia_pago_2,
        deuda_inicial=Decimal(str(o.deuda_inicial)),
        fecha_deuda_inicial=o.fecha_deuda_inicial,
        activa=o.activa,
    )


def _to_domain(m: ObligacionHotelModel) -> ObligacionHotel:
    return ObligacionHotel(
        id=m.id,
        punto_de_venta_nombre=m.punto_de_venta_nombre,
        receptor_nombre=m.receptor_nombre,
        monto_cuota_dia_1=Dinero(m.monto_cuota_dia_1),
        monto_cuota_dia_2=(
            Dinero(m.monto_cuota_dia_2) if m.monto_cuota_dia_2 is not None else None
        ),
        dia_pago_1=m.dia_pago_1,
        dia_pago_2=m.dia_pago_2,
        deuda_inicial=Dinero(m.deuda_inicial),
        fecha_deuda_inicial=m.fecha_deuda_inicial,
        activa=m.activa,
    )


class SQLAObligacionHotelRepository(ObligacionHotelRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def listar_activas(self) -> list[ObligacionHotel]:
        with self._sf.begin() as session:
            stmt = (
                select(ObligacionHotelModel)
                .where(ObligacionHotelModel.activa == True)
                .order_by(ObligacionHotelModel.punto_de_venta_nombre)
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_domain(r) for r in rows]

    def buscar_por_id(self, id: uuid.UUID) -> ObligacionHotel | None:
        with self._sf.begin() as session:
            m = session.get(ObligacionHotelModel, id)
            return _to_domain(m) if m else None

    def guardar(self, obligacion: ObligacionHotel) -> None:
        with self._sf.begin() as session:
            session.merge(_to_orm(obligacion))
