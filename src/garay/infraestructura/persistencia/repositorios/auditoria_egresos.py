from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.conciliacion.auditoria_egreso import AuditoriaEgreso
from garay.dominio.puertos.repositorios import AuditoriaEgresoRepository
from garay.infraestructura.persistencia.modelos import AuditoriaEgresoModel


def to_orm(registro: AuditoriaEgreso) -> AuditoriaEgresoModel:
    return AuditoriaEgresoModel(
        id=registro.id,
        egreso_id=registro.egreso_id,
        campo=registro.campo,
        valor_anterior=registro.valor_anterior,
        valor_nuevo=registro.valor_nuevo,
        realizada_por_telegram_id=registro.realizada_por_telegram_id,
        realizada_por_nombre=registro.realizada_por_nombre,
        realizada_at=registro.realizada_at,
    )


def to_domain(m: AuditoriaEgresoModel) -> AuditoriaEgreso:
    return AuditoriaEgreso(
        id=m.id,
        egreso_id=m.egreso_id,
        campo=m.campo,
        valor_anterior=m.valor_anterior,
        valor_nuevo=m.valor_nuevo,
        realizada_por_telegram_id=m.realizada_por_telegram_id,
        realizada_por_nombre=m.realizada_por_nombre,
        realizada_at=m.realizada_at,
    )


class SQLAAuditoriaEgresoRepository(AuditoriaEgresoRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, registro: AuditoriaEgreso) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(registro))

    def listar_por_egreso_id(self, egreso_id: uuid.UUID) -> list[AuditoriaEgreso]:
        with self._sf.begin() as session:
            stmt = (
                select(AuditoriaEgresoModel)
                .where(AuditoriaEgresoModel.egreso_id == egreso_id)
                .order_by(AuditoriaEgresoModel.realizada_at)
            )
            rows = session.execute(stmt).scalars().all()
            return [to_domain(r) for r in rows]
