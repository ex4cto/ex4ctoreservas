"""SQLAlchemy adapter for AuditoriaEntidadesRepository port.

Mirrors the auditoria_egresos adapter pattern: to_orm / to_domain helpers
plus a repository class that accepts a sessionmaker.
"""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.auditoria.entidades import RegistroAuditoria
from garay.dominio.puertos.repositorios import AuditoriaEntidadesRepository
from garay.infraestructura.persistencia.modelos import AuditoriaEntidadModel


def to_orm(registro: RegistroAuditoria) -> AuditoriaEntidadModel:
    return AuditoriaEntidadModel(
        id=registro.id,
        entidad_tipo=registro.entidad_tipo,
        entidad_id=registro.entidad_id,
        entidad_clave=registro.entidad_clave,
        campo=registro.campo,
        valor_anterior=registro.valor_anterior,
        valor_nuevo=registro.valor_nuevo,
        realizada_por_telegram_id=registro.realizada_por_telegram_id,
        realizada_por_nombre=registro.realizada_por_nombre,
        realizada_at=registro.realizada_at,
    )


def to_domain(m: AuditoriaEntidadModel) -> RegistroAuditoria:
    return RegistroAuditoria(
        id=m.id,
        entidad_tipo=m.entidad_tipo,
        entidad_id=m.entidad_id,
        entidad_clave=m.entidad_clave,
        campo=m.campo,
        valor_anterior=m.valor_anterior,
        valor_nuevo=m.valor_nuevo,
        realizada_por_telegram_id=m.realizada_por_telegram_id,
        realizada_por_nombre=m.realizada_por_nombre,
        realizada_at=m.realizada_at,
    )


class SQLAAuditoriaEntidadesRepository(AuditoriaEntidadesRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, registro: RegistroAuditoria) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(registro))

    def listar(
        self,
        *,
        entidad_tipo: str | None = None,
        por_telegram_id: int | None = None,
        desde: datetime.date | None = None,
        hasta: datetime.date | None = None,
    ) -> list[RegistroAuditoria]:
        with self._sf.begin() as session:
            stmt = select(AuditoriaEntidadModel)
            if entidad_tipo is not None:
                stmt = stmt.where(AuditoriaEntidadModel.entidad_tipo == entidad_tipo)
            if por_telegram_id is not None:
                stmt = stmt.where(
                    AuditoriaEntidadModel.realizada_por_telegram_id == por_telegram_id
                )
            if desde is not None:
                # Use timezone-naive start-of-day for compatibility with both
                # SQLite (stores naive) and PostgreSQL (timezone-aware).
                desde_dt = datetime.datetime(desde.year, desde.month, desde.day, 0, 0, 0)
                stmt = stmt.where(AuditoriaEntidadModel.realizada_at >= desde_dt)
            if hasta is not None:
                hasta_dt = datetime.datetime(
                    hasta.year, hasta.month, hasta.day, 23, 59, 59
                )
                stmt = stmt.where(AuditoriaEntidadModel.realizada_at <= hasta_dt)
            stmt = stmt.order_by(AuditoriaEntidadModel.realizada_at.desc())
            rows = session.execute(stmt).scalars().all()
            return [to_domain(r) for r in rows]
