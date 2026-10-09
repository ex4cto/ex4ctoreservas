"""SQLAlchemy implementation of PagoFreelancerRepository."""

from __future__ import annotations

import datetime
import uuid
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.liquidaciones.entidades import PagoFreelancer
from garay.dominio.puertos.repositorios import PagoFreelancerRepository
from garay.infraestructura.persistencia.modelos import PagoFreelancerModel


def _to_orm(pago: PagoFreelancer) -> PagoFreelancerModel:
    return PagoFreelancerModel(
        id=pago.id,
        freelancer_id=pago.freelancer_id,
        monto=pago.monto,
        desde=pago.desde,
        hasta=pago.hasta,
        fecha_pago=pago.fecha_pago,
        registrado_por_telegram_id=pago.registrado_por_telegram_id,
        registrado_por_nombre=pago.registrado_por_nombre,
    )


def _to_domain(m: PagoFreelancerModel) -> PagoFreelancer:
    return PagoFreelancer(
        id=m.id,
        freelancer_id=m.freelancer_id,
        monto=m.monto,
        desde=m.desde,
        hasta=m.hasta,
        fecha_pago=m.fecha_pago,
        registrado_por_telegram_id=m.registrado_por_telegram_id,
        registrado_por_nombre=m.registrado_por_nombre,
    )


class PagoFreelancerSQLAlchemy(PagoFreelancerRepository):
    """SQLAlchemy-backed implementation of PagoFreelancerRepository."""

    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, pago: PagoFreelancer) -> None:
        with self._sf.begin() as session:
            session.merge(_to_orm(pago))

    def listar_por_freelancer(
        self,
        freelancer_id: uuid.UUID,
        desde: date,
        hasta: date,
    ) -> list[PagoFreelancer]:
        """Return pagos for the freelancer whose period overlaps [desde, hasta]."""
        with self._sf.begin() as session:
            stmt = (
                select(PagoFreelancerModel)
                .where(
                    PagoFreelancerModel.freelancer_id == freelancer_id,
                    PagoFreelancerModel.desde <= hasta,
                    PagoFreelancerModel.hasta >= desde,
                )
                .order_by(PagoFreelancerModel.fecha_pago.desc())
            )
            return [_to_domain(m) for m in session.scalars(stmt).all()]

    def buscar_solapados(
        self,
        freelancer_id: uuid.UUID,
        desde: date,
        hasta: date,
    ) -> list[PagoFreelancer]:
        """Return pagos that overlap with the given period.

        SQL condition: WHERE freelancer_id = :id AND desde <= :hasta AND hasta >= :desde
        """
        with self._sf.begin() as session:
            stmt = (
                select(PagoFreelancerModel)
                .where(
                    PagoFreelancerModel.freelancer_id == freelancer_id,
                    PagoFreelancerModel.desde <= hasta,
                    PagoFreelancerModel.hasta >= desde,
                )
                .order_by(PagoFreelancerModel.fecha_pago.desc())
            )
            return [_to_domain(m) for m in session.scalars(stmt).all()]

    def eliminar(self, pago_id: uuid.UUID) -> None:
        with self._sf.begin() as session:
            session.execute(
                delete(PagoFreelancerModel).where(PagoFreelancerModel.id == pago_id)
            )
