"""SQLAlchemy implementation of IngresoRepository."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Ingreso
from garay.dominio.puertos.repositorios import IngresoRepository
from garay.infraestructura.persistencia.modelos import IngresoModel

_UTC = datetime.UTC


def _to_orm(ingreso: Ingreso) -> IngresoModel:
    return IngresoModel(
        id=ingreso.id,
        banco=ingreso.banco,
        monto=ingreso.monto,
        fecha=ingreso.fecha,
        referencia=ingreso.referencia,
        remitente=ingreso.remitente,
        clasificado=ingreso.clasificado,
        venta_id=ingreso.venta_id,
        fecha_recibido=ingreso.fecha_recibido,
    )


def _to_domain(m: IngresoModel) -> Ingreso:
    return Ingreso(
        id=m.id,
        banco=m.banco,
        monto=m.monto if isinstance(m.monto, Dinero) else Dinero(str(m.monto)),
        fecha=m.fecha,
        referencia=m.referencia,
        remitente=m.remitente,
        clasificado=m.clasificado,
        venta_id=m.venta_id,
        fecha_recibido=m.fecha_recibido,
    )


class SQLAIngresoRepository(IngresoRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, ingreso: Ingreso) -> None:
        with self._sf.begin() as session:
            session.merge(_to_orm(ingreso))

    def buscar_por_id(self, id: uuid.UUID) -> Ingreso | None:
        with self._sf.begin() as session:
            m = session.get(IngresoModel, id)
            return _to_domain(m) if m else None

    def listar_sin_clasificar(self) -> list[Ingreso]:
        with self._sf.begin() as session:
            stmt = select(IngresoModel).where(IngresoModel.clasificado == False)  # noqa: E712
            rows = session.execute(stmt).scalars().all()
            return [_to_domain(r) for r in rows]

    def existe_referencia(self, referencia: str) -> bool:
        with self._sf.begin() as session:
            stmt = select(IngresoModel.id).where(IngresoModel.referencia == referencia).limit(1)
            result = session.execute(stmt).scalar_one_or_none()
            return result is not None

    def listar_recientes(self, minutos: int) -> list[Ingreso]:
        """Return ingresos with fecha_recibido within the last *minutos* minutes."""
        desde = datetime.datetime.now(_UTC) - datetime.timedelta(minutes=minutos)
        with self._sf.begin() as session:
            stmt = (
                select(IngresoModel)
                .where(IngresoModel.fecha_recibido.isnot(None))
                .where(IngresoModel.fecha_recibido >= desde)
                .order_by(IngresoModel.fecha_recibido.desc())
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_domain(r) for r in rows]
