from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.puertos.repositorios import ServicioRepository
from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.persistencia.modelos import ServicioModel


def to_orm(s: Servicio) -> ServicioModel:
    return ServicioModel(
        id=s.id,
        numero=s.numero,
        nombre=s.nombre,
        descripcion=s.descripcion,
        activo=s.activo,
        precio_neto_adulto=s.precio_neto_adulto,
        precio_neto_nino=s.precio_neto_nino,
        categoria=s.categoria,
        horarios=s.horarios,
    )


def to_domain(m: ServicioModel) -> Servicio:
    return Servicio(
        id=m.id,
        numero=m.numero,
        nombre=m.nombre,
        descripcion=m.descripcion,
        activo=m.activo,
        precio_neto_adulto=m.precio_neto_adulto,
        precio_neto_nino=m.precio_neto_nino,
        categoria=m.categoria,
        horarios=list(m.horarios) if m.horarios else [],
    )


class SQLAServicioRepository(ServicioRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, servicio: Servicio) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(servicio))

    def buscar_por_id(self, id: uuid.UUID) -> Servicio | None:
        with self._sf.begin() as session:
            m = session.get(ServicioModel, id)
            return to_domain(m) if m else None

    def buscar_por_nombre(self, nombre: str) -> Servicio | None:
        with self._sf.begin() as session:
            row = session.execute(
                select(ServicioModel).where(ServicioModel.nombre == nombre)
            ).scalar_one_or_none()
            return to_domain(row) if row else None

    def listar(self) -> list[Servicio]:
        with self._sf.begin() as session:
            rows = session.execute(select(ServicioModel)).scalars().all()
            return [to_domain(r) for r in rows]

    def listar_activos(self) -> list[Servicio]:
        with self._sf.begin() as session:
            rows = (
                session.execute(
                    select(ServicioModel).where(ServicioModel.activo.is_(True))
                )
                .scalars()
                .all()
            )
            return [to_domain(r) for r in rows]

    def siguiente_numero(self) -> int:
        with self._sf.begin() as session:
            maximo = session.execute(
                select(func.max(ServicioModel.numero))
            ).scalar_one()
            return int(maximo) + 1 if maximo is not None else 1
