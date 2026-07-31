"""SQLAlchemy implementation of FacturaRepository."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.facturas.entidades import Factura
from garay.dominio.facturas.tipos import EstadoEnvioFactura
from garay.dominio.puertos.repositorios import FacturaRepository
from garay.infraestructura.persistencia.modelos import FacturaModel


def _to_orm(factura: Factura) -> FacturaModel:
    return FacturaModel(
        id=factura.id,
        numero=factura.numero,
        venta_id=factura.venta_id,
        cliente_nombre=factura.cliente_nombre,
        cliente_email=factura.cliente_email,
        monto_total=factura.monto_total,
        abono=factura.abono,
        fecha_emision=factura.fecha_emision,
        html_contenido=factura.html_contenido,
        estado_envio=str(factura.estado_envio),
    )


def _to_domain(m: FacturaModel) -> Factura:
    return Factura(
        id=m.id,
        numero=m.numero,
        venta_id=m.venta_id,
        cliente_nombre=m.cliente_nombre,
        cliente_email=m.cliente_email,
        monto_total=m.monto_total,
        abono=m.abono,
        fecha_emision=m.fecha_emision,
        html_contenido=m.html_contenido,
        estado_envio=EstadoEnvioFactura(m.estado_envio),
    )


class SQLAFacturaRepository(FacturaRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, factura: Factura) -> None:
        with self._sf.begin() as session:
            session.merge(_to_orm(factura))

    def buscar_por_id(self, id: uuid.UUID) -> Factura | None:
        with self._sf.begin() as session:
            m = session.get(FacturaModel, id)
            return _to_domain(m) if m else None

    def buscar_por_venta_id(self, venta_id: uuid.UUID) -> Factura | None:
        with self._sf.begin() as session:
            row = session.execute(
                select(FacturaModel).where(FacturaModel.venta_id == venta_id)
            ).scalar_one_or_none()
            return _to_domain(row) if row else None

    def listar_por_periodo(
        self, desde: datetime.date, hasta: datetime.date
    ) -> list[Factura]:
        with self._sf.begin() as session:
            stmt = (
                select(FacturaModel)
                .where(
                    FacturaModel.fecha_emision >= desde,
                    FacturaModel.fecha_emision <= hasta,
                )
                .order_by(FacturaModel.fecha_emision)
            )
            return [_to_domain(m) for m in session.scalars(stmt).all()]
