from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.tipos import EstadoVenta, TipoCliente
from garay.dominio.puertos.repositorios import VentaRepository
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes
from garay.infraestructura.persistencia.modelos import VentaModel


def to_orm(v: Venta) -> VentaModel:
    return VentaModel(
        id=v.id,
        valor_venta=v.valor_venta,
        neto=v.neto,
        abono=v.abono,
        servicio_ids=[str(uid) for uid in v.servicio_ids],
        cliente_id=v.cliente_id,
        tipo_cliente=str(v.tipo_cliente),
        fecha=v.fecha,
        adultos=v.adultos,
        ninos=v.ninos,
        estado=str(v.estado),
        vendedor_nombre=v.participantes.vendedor_nombre,
        cerrador_nombre=v.participantes.cerrador_nombre,
        punto_de_venta_id=v.participantes.punto_de_venta_id,
        referido_nombre=v.participantes.referido_nombre,
    )


def to_domain(m: VentaModel) -> Venta:
    return Venta(
        id=m.id,
        valor_venta=m.valor_venta,
        neto=m.neto,
        abono=m.abono,
        servicio_ids=[uuid.UUID(s) for s in m.servicio_ids],
        cliente_id=m.cliente_id,
        tipo_cliente=TipoCliente(m.tipo_cliente),
        fecha=m.fecha,
        adultos=m.adultos,
        ninos=m.ninos,
        estado=EstadoVenta(m.estado),
        participantes=Participantes(
            vendedor_nombre=m.vendedor_nombre,
            cerrador_nombre=m.cerrador_nombre,
            punto_de_venta_id=m.punto_de_venta_id,
            referido_nombre=m.referido_nombre,
        ),
    )


class SQLAVentaRepository(VentaRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, venta: Venta) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(venta))

    def buscar_por_id(self, id: uuid.UUID) -> Venta | None:
        with self._sf.begin() as session:
            m = session.get(VentaModel, id)
            return to_domain(m) if m else None

    def listar(self) -> list[Venta]:
        with self._sf.begin() as session:
            rows = session.execute(select(VentaModel)).scalars().all()
            return [to_domain(r) for r in rows]

    def listar_por_freelancer_y_periodo(self, nombre: str, desde: date, hasta: date) -> list[Venta]:
        with self._sf.begin() as session:
            stmt = (
                select(VentaModel)
                .where(
                    (VentaModel.vendedor_nombre == nombre) | (VentaModel.cerrador_nombre == nombre)
                )
                .where(VentaModel.fecha >= desde)
                .where(VentaModel.fecha <= hasta)
            )
            rows = session.execute(stmt).scalars().all()
            return [to_domain(r) for r in rows]

    def listar_por_periodo(self, desde: date, hasta: date) -> list[Venta]:
        with self._sf.begin() as session:
            stmt = (
                select(VentaModel)
                .where(VentaModel.fecha >= desde)
                .where(VentaModel.fecha <= hasta)
            )
            rows = session.execute(stmt).scalars().all()
            return [to_domain(r) for r in rows]
