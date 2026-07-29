"""SQLAlchemy implementation of EgresoRepository."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

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

    def listar_por_periodo(self, desde: datetime.date, hasta: datetime.date) -> list[Egreso]:
        with self._sf.begin() as session:
            stmt = (
                select(EgresoModel)
                .where(EgresoModel.fecha >= desde, EgresoModel.fecha <= hasta)
                .order_by(EgresoModel.fecha)
            )
            return [_to_domain(m) for m in session.scalars(stmt).all()]
