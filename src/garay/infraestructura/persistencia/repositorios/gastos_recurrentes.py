"""SQLAlchemy implementation of GastoRecurrenteRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.conciliacion.entidades import GastoRecurrente
from garay.dominio.puertos.repositorios import GastoRecurrenteRepository
from garay.infraestructura.persistencia.modelos import GastoRecurrenteModel


def _to_orm(gasto: GastoRecurrente) -> GastoRecurrenteModel:
    return GastoRecurrenteModel(
        id=gasto.id,
        nombre=gasto.nombre,
        monto=gasto.monto,
        categoria=gasto.categoria,
        dia_mes=gasto.dia_mes,
        activo=gasto.activo,
    )


def _to_domain(m: GastoRecurrenteModel) -> GastoRecurrente:
    return GastoRecurrente(
        id=m.id,
        nombre=m.nombre,
        monto=m.monto,
        categoria=m.categoria,
        dia_mes=m.dia_mes,
        activo=m.activo,
    )


class SQLAGastoRecurrenteRepository(GastoRecurrenteRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, gasto: GastoRecurrente) -> None:
        with self._sf.begin() as session:
            session.merge(_to_orm(gasto))

    def buscar_por_id(self, id: uuid.UUID) -> GastoRecurrente | None:
        with self._sf.begin() as session:
            m = session.get(GastoRecurrenteModel, id)
            return _to_domain(m) if m else None

    def listar_activos(self) -> list[GastoRecurrente]:
        with self._sf.begin() as session:
            stmt = (
                select(GastoRecurrenteModel)
                .where(GastoRecurrenteModel.activo == True)  # noqa: E712
                .order_by(GastoRecurrenteModel.nombre)
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_domain(r) for r in rows]

    def desactivar(self, id: uuid.UUID) -> None:
        with self._sf.begin() as session:
            stmt = (
                update(GastoRecurrenteModel)
                .where(GastoRecurrenteModel.id == id)
                .values(activo=False)
            )
            session.execute(stmt)
