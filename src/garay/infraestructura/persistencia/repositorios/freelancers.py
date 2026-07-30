from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.puertos.repositorios import FreelancerRepository
from garay.infraestructura.persistencia.modelos import FreelancerModel


def to_orm(f: Freelancer) -> FreelancerModel:
    return FreelancerModel(
        id=f.id,
        nombre=f.nombre,
        activo=f.activo,
        telegram_user_id=f.telegram_user_id,
        es_admin=f.es_admin,
    )


def to_domain(m: FreelancerModel) -> Freelancer:
    return Freelancer(
        id=m.id,
        nombre=m.nombre,
        activo=m.activo,
        telegram_user_id=m.telegram_user_id,
        es_admin=m.es_admin,
    )


class SQLAFreelancerRepository(FreelancerRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, freelancer: Freelancer) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(freelancer))

    def buscar_por_id(self, id: uuid.UUID) -> Freelancer | None:
        with self._sf.begin() as session:
            m = session.get(FreelancerModel, id)
            return to_domain(m) if m else None

    def listar_activos(self) -> list[Freelancer]:
        with self._sf.begin() as session:
            rows = (
                session.execute(select(FreelancerModel).where(FreelancerModel.activo.is_(True)))
                .scalars()
                .all()
            )
            return [to_domain(r) for r in rows]

    def buscar_por_telegram_id(self, telegram_user_id: int) -> Freelancer | None:
        with self._sf.begin() as session:
            row = session.execute(
                select(FreelancerModel)
                .where(FreelancerModel.telegram_user_id == telegram_user_id)
                .where(FreelancerModel.activo.is_(True))
            ).scalar_one_or_none()
            return to_domain(row) if row else None

    def buscar_por_nombre(self, nombre: str) -> Freelancer | None:
        with self._sf.begin() as session:
            row = session.execute(
                select(FreelancerModel).where(FreelancerModel.nombre == nombre)
            ).scalar_one_or_none()
            return to_domain(row) if row else None

    def listar_todos(self) -> list[Freelancer]:
        with self._sf.begin() as session:
            rows = (
                session.execute(
                    select(FreelancerModel).order_by(FreelancerModel.nombre)
                )
                .scalars()
                .all()
            )
            return [to_domain(r) for r in rows]
