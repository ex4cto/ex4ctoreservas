"""SQLAlchemy implementation of PagoReferidoRepository."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.liquidaciones.entidades import PagoReferido
from garay.dominio.puertos.repositorios import PagoReferidoRepository
from garay.infraestructura.persistencia.modelos import PagoReferidoModel


def _to_orm(p: PagoReferido) -> PagoReferidoModel:
    return PagoReferidoModel(
        id=p.id,
        venta_id=p.venta_id,
        referido_alias=p.referido_alias,
        monto=p.monto,
        fecha_pago=p.fecha_pago,
        registrado_por_telegram_id=p.registrado_por_telegram_id,
        registrado_por_nombre=p.registrado_por_nombre,
    )


def _to_domain(m: PagoReferidoModel) -> PagoReferido:
    return PagoReferido(
        id=m.id,
        venta_id=m.venta_id,
        referido_alias=m.referido_alias,
        monto=m.monto,
        fecha_pago=m.fecha_pago,
        registrado_por_telegram_id=m.registrado_por_telegram_id,
        registrado_por_nombre=m.registrado_por_nombre,
    )


class SQLAPagoReferidoRepository(PagoReferidoRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, pago: PagoReferido) -> None:
        with self._sf.begin() as session:
            session.merge(_to_orm(pago))

    def listar_por_venta(self, venta_id: uuid.UUID) -> list[PagoReferido]:
        with self._sf.begin() as session:
            rows = session.execute(
                select(PagoReferidoModel).where(PagoReferidoModel.venta_id == venta_id)
            ).scalars().all()
            return [_to_domain(r) for r in rows]

    def listar_por_referido(self, referido_alias: str) -> list[PagoReferido]:
        with self._sf.begin() as session:
            rows = session.execute(
                select(PagoReferidoModel).where(
                    PagoReferidoModel.referido_alias == referido_alias
                )
            ).scalars().all()
            return [_to_domain(r) for r in rows]

    def buscar_solapados(
        self, referido_alias: str, desde: date, hasta: date
    ) -> list[PagoReferido]:
        """Return pagos for alias whose fecha_pago falls within [desde, hasta].

        Since PagoReferido is per-venta (no desde/hasta period), overlap is
        detected by checking if the fecha_pago date falls within the query range.
        SQL: WHERE referido_alias = :alias AND DATE(fecha_pago) BETWEEN :desde AND :hasta
        """
        from sqlalchemy import func as sqlfunc

        with self._sf.begin() as session:
            rows = session.execute(
                select(PagoReferidoModel).where(
                    PagoReferidoModel.referido_alias == referido_alias,
                    sqlfunc.date(PagoReferidoModel.fecha_pago) >= desde,
                    sqlfunc.date(PagoReferidoModel.fecha_pago) <= hasta,
                )
            ).scalars().all()
            return [_to_domain(r) for r in rows]

    def eliminar(self, pago_id: uuid.UUID) -> None:
        with self._sf.begin() as session:
            session.execute(
                delete(PagoReferidoModel).where(PagoReferidoModel.id == pago_id)
            )
