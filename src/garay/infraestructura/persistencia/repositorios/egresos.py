"""SQLAlchemy implementation of EgresoRepository."""

from __future__ import annotations

import calendar
import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.dominio.puertos.repositorios import EgresoRepository
from garay.infraestructura.persistencia.modelos import EgresoModel

_UTC = datetime.UTC


def _to_orm(egreso: Egreso) -> EgresoModel:
    return EgresoModel(
        id=egreso.id,
        descripcion=egreso.descripcion,
        monto=egreso.monto,
        fecha=egreso.fecha,
        categoria=str(egreso.categoria),
        tipo=str(egreso.tipo),
        referencia=egreso.referencia,
        fecha_recibido=egreso.fecha_recibido,
        correo_origen=egreso.correo_origen,
        reenviado=egreso.reenviado,
        gasto_recurrente_id=egreso.gasto_recurrente_id,
        destinatario=egreso.destinatario,
    )


def _to_domain(m: EgresoModel) -> Egreso:
    return Egreso(
        id=m.id,
        descripcion=m.descripcion,
        monto=m.monto,
        fecha=m.fecha,
        categoria=m.categoria,
        tipo=TipoEgreso(m.tipo),
        referencia=m.referencia,
        fecha_recibido=m.fecha_recibido,
        correo_origen=m.correo_origen,
        reenviado=m.reenviado,
        gasto_recurrente_id=m.gasto_recurrente_id,
        destinatario=m.destinatario,
    )


class SQLAEgresoRepository(EgresoRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, egreso: Egreso) -> None:
        with self._sf.begin() as session:
            session.merge(_to_orm(egreso))

    def buscar_por_id(self, id: uuid.UUID) -> Egreso | None:
        with self._sf.begin() as session:
            m = session.get(EgresoModel, id)
            return _to_domain(m) if m else None

    def existe_referencia(self, referencia: str) -> bool:
        with self._sf.begin() as session:
            stmt = (
                select(EgresoModel.id)
                .where(EgresoModel.referencia == referencia)
                .limit(1)
            )
            result = session.execute(stmt).scalar_one_or_none()
            return result is not None

    def listar_recientes(self, minutos: int) -> list[Egreso]:
        """Return egresos with fecha_recibido within the last *minutos* minutes."""
        desde = datetime.datetime.now(_UTC) - datetime.timedelta(minutes=minutos)
        with self._sf.begin() as session:
            stmt = (
                select(EgresoModel)
                .where(EgresoModel.fecha_recibido.isnot(None))
                .where(EgresoModel.fecha_recibido >= desde)
                .order_by(EgresoModel.fecha_recibido.desc())
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_domain(r) for r in rows]

    def listar_por_periodo(self, desde: datetime.date, hasta: datetime.date) -> list[Egreso]:
        with self._sf.begin() as session:
            stmt = (
                select(EgresoModel)
                .where(EgresoModel.fecha >= desde, EgresoModel.fecha <= hasta)
                .order_by(EgresoModel.fecha)
            )
            return [_to_domain(m) for m in session.scalars(stmt).all()]

    def sumar_por_recurrente_en_mes(
        self,
        gasto_recurrente_id: uuid.UUID,
        año: int,
        mes: int,
    ) -> Dinero:
        inicio = datetime.date(año, mes, 1)
        fin = datetime.date(año, mes, calendar.monthrange(año, mes)[1])
        with self._sf.begin() as session:
            stmt = (
                select(EgresoModel)
                .where(
                    EgresoModel.gasto_recurrente_id == gasto_recurrente_id,
                    EgresoModel.fecha >= inicio,
                    EgresoModel.fecha <= fin,
                )
            )
            rows = session.scalars(stmt).all()
            return sum((r.monto for r in rows), start=Dinero(0))
