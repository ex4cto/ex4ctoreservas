from __future__ import annotations

import datetime
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
        canal_origen=v.canal_origen,
        fechas_por_servicio=(
            {str(k): val.isoformat() for k, val in v.fechas_por_servicio.items()}
            if v.fechas_por_servicio is not None
            else None
        ),
        horarios_por_servicio=(
            {str(k): val for k, val in v.horarios_por_servicio.items()}
            if v.horarios_por_servicio is not None
            else None
        ),
        vendedor_id=v.participantes.vendedor_id,
        cerrador_id=v.participantes.cerrador_id,
        anulada=v.anulada,
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
        canal_origen=m.canal_origen,
        fechas_por_servicio=(
            {
                uuid.UUID(k): datetime.datetime.fromisoformat(v)
                for k, v in m.fechas_por_servicio.items()
            }
            if m.fechas_por_servicio is not None
            else None
        ),
        horarios_por_servicio=(
            {uuid.UUID(k): val for k, val in m.horarios_por_servicio.items()}
            if m.horarios_por_servicio is not None
            else None
        ),
        participantes=Participantes(
            vendedor_nombre=m.vendedor_nombre,
            cerrador_nombre=m.cerrador_nombre,
            punto_de_venta_id=m.punto_de_venta_id,
            referido_nombre=m.referido_nombre,
            vendedor_id=m.vendedor_id,
            cerrador_id=m.cerrador_id,
        ),
        anulada=m.anulada,
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
            stmt = select(VentaModel).where(VentaModel.anulada == False)  # noqa: E712
            rows = session.execute(stmt).scalars().all()
            return [to_domain(r) for r in rows]

    def listar_por_freelancer_y_periodo(
        self,
        freelancer_id: uuid.UUID,
        nombre: str,
        desde: date,
        hasta: date,
    ) -> list[Venta]:
        with self._sf.begin() as session:
            stmt = (
                select(VentaModel)
                .where(VentaModel.anulada == False)  # noqa: E712
                .where(
                    # Stricter 4-clause: name-match ONLY when id column IS NULL
                    (VentaModel.vendedor_id == freelancer_id)
                    | (VentaModel.cerrador_id == freelancer_id)
                    | (
                        (VentaModel.vendedor_id == None)  # noqa: E711
                        & (VentaModel.vendedor_nombre == nombre)
                    )
                    | (
                        (VentaModel.cerrador_id == None)  # noqa: E711
                        & (VentaModel.cerrador_nombre == nombre)
                    )
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
                .where(VentaModel.anulada == False)  # noqa: E712
                .where(VentaModel.fecha >= desde)
                .where(VentaModel.fecha <= hasta)
            )
            rows = session.execute(stmt).scalars().all()
            return [to_domain(r) for r in rows]
