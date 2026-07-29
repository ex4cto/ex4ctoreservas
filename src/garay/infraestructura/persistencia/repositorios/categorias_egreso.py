"""SQLAlchemy implementation of CategoriaEgresoRepository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.conciliacion.entidades import CategoriaEgreso
from garay.dominio.puertos.repositorios import CategoriaEgresoRepository
from garay.infraestructura.persistencia.modelos import CategoriaEgresoModel


def _to_orm(cat: CategoriaEgreso) -> CategoriaEgresoModel:
    return CategoriaEgresoModel(
        nombre=cat.nombre,
        descripcion=cat.descripcion,
        activo=cat.activo,
        orden=cat.orden,
    )


def _to_domain(m: CategoriaEgresoModel) -> CategoriaEgreso:
    return CategoriaEgreso(
        nombre=m.nombre,
        descripcion=m.descripcion,
        activo=m.activo,
        orden=m.orden,
    )


class SQLACategoriaEgresoRepository(CategoriaEgresoRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def listar_activas(self) -> list[str]:
        with self._sf.begin() as session:
            stmt = (
                select(CategoriaEgresoModel)
                .where(CategoriaEgresoModel.activo == True)  # noqa: E712
                .order_by(CategoriaEgresoModel.orden, CategoriaEgresoModel.nombre)
            )
            rows = session.execute(stmt).scalars().all()
            return [r.nombre for r in rows]

    def guardar(self, categoria: CategoriaEgreso) -> None:
        with self._sf.begin() as session:
            session.merge(_to_orm(categoria))
