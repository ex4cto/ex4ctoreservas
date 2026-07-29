"""SQLAlchemy implementation of ConciliacionRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.conciliacion.entidades import Conciliacion
from garay.dominio.conciliacion.tipos import EstadoConciliacion
from garay.dominio.puertos.repositorios import ConciliacionRepository
from garay.infraestructura.persistencia.modelos import ConciliacionModel


class SQLAConciliacionRepository(ConciliacionRepository):
    """Implementacion de ConciliacionRepository usando SQLAlchemy."""

    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, conciliacion: Conciliacion) -> None:
        with self._sf.begin() as session:
            model = session.get(ConciliacionModel, conciliacion.id)
            if model is None:
                model = ConciliacionModel(id=conciliacion.id)
                session.add(model)
            model.ingreso_id = conciliacion.ingreso_id
            model.venta_id = conciliacion.venta_id
            model.estado = str(conciliacion.estado)
            model.notas = conciliacion.notas
            model.score = conciliacion.score
            model.confianza = conciliacion.confianza

    def buscar_por_ingreso_id(self, ingreso_id: uuid.UUID) -> Conciliacion | None:
        with self._sf.begin() as session:
            stmt = select(ConciliacionModel).where(
                ConciliacionModel.ingreso_id == ingreso_id
            )
            model = session.scalar(stmt)
            return self._to_entity(model) if model else None

    def buscar_por_id(self, id: uuid.UUID) -> Conciliacion | None:
        with self._sf.begin() as session:
            model = session.get(ConciliacionModel, id)
            return self._to_entity(model) if model else None

    def listar_pendientes(self) -> list[Conciliacion]:
        with self._sf.begin() as session:
            stmt = select(ConciliacionModel).where(
                ConciliacionModel.estado.in_([
                    EstadoConciliacion.PENDIENTE,
                    EstadoConciliacion.SIN_MATCH,
                ])
            )
            return [self._to_entity(m) for m in session.scalars(stmt).all()]

    def listar_ingreso_ids_procesados(self) -> list[uuid.UUID]:
        with self._sf.begin() as session:
            stmt = select(ConciliacionModel.ingreso_id)
            return list(session.scalars(stmt).all())

    @staticmethod
    def _to_entity(model: ConciliacionModel) -> Conciliacion:
        return Conciliacion(
            id=model.id,
            ingreso_id=model.ingreso_id,
            venta_id=model.venta_id,
            estado=EstadoConciliacion(model.estado),
            notas=model.notas,
            score=model.score,
            confianza=model.confianza,
        )
