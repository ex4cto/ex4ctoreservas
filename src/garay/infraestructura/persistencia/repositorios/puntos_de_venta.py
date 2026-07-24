from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.puertos.repositorios import PuntoDeVentaRepository
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.infraestructura.persistencia.modelos import PuntoDeVentaModel


def to_orm(p: PuntoDeVenta) -> PuntoDeVentaModel:
    return PuntoDeVentaModel(
        id=p.id,
        nombre=p.nombre,
        porcentaje_capa=p.porcentaje_capa,
    )


def to_domain(m: PuntoDeVentaModel) -> PuntoDeVenta:
    return PuntoDeVenta(
        id=m.id,
        nombre=m.nombre,
        porcentaje_capa=m.porcentaje_capa,
    )


class SQLAPuntoDeVentaRepository(PuntoDeVentaRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, punto: PuntoDeVenta) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(punto))

    def buscar_por_id(self, id: uuid.UUID) -> PuntoDeVenta | None:
        with self._sf.begin() as session:
            m = session.get(PuntoDeVentaModel, id)
            return to_domain(m) if m else None

    def listar(self) -> list[PuntoDeVenta]:
        with self._sf.begin() as session:
            rows = session.execute(select(PuntoDeVentaModel)).scalars().all()
            return [to_domain(r) for r in rows]
