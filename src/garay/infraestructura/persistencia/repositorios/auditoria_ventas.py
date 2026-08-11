from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.puertos.repositorios import AuditoriaVentaRepository
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.infraestructura.persistencia.modelos import AuditoriaVentaModel


def to_orm(registro: AuditoriaVenta) -> AuditoriaVentaModel:
    return AuditoriaVentaModel(
        id=registro.id,
        venta_id=registro.venta_id,
        accion=str(registro.accion),
        motivo=registro.motivo,
        realizada_por_telegram_id=registro.realizada_por_telegram_id,
        realizada_por_nombre=registro.realizada_por_nombre,
        realizada_at=registro.realizada_at,
        datos_previos=registro.datos_previos,
    )


def to_domain(m: AuditoriaVentaModel) -> AuditoriaVenta:
    return AuditoriaVenta(
        id=m.id,
        venta_id=m.venta_id,
        accion=AccionAuditoria(m.accion),
        motivo=m.motivo,
        realizada_por_telegram_id=m.realizada_por_telegram_id,
        realizada_por_nombre=m.realizada_por_nombre,
        realizada_at=m.realizada_at,
        datos_previos=m.datos_previos,
    )


class SQLAAuditoriaVentaRepository(AuditoriaVentaRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, registro: AuditoriaVenta) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(registro))

    def listar_por_venta_id(self, venta_id: uuid.UUID) -> list[AuditoriaVenta]:
        with self._sf.begin() as session:
            stmt = (
                select(AuditoriaVentaModel)
                .where(AuditoriaVentaModel.venta_id == venta_id)
                .order_by(AuditoriaVentaModel.realizada_at)
            )
            rows = session.execute(stmt).scalars().all()
            return [to_domain(r) for r in rows]
