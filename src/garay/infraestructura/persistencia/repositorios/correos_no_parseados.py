"""SQLAlchemy implementation of CorreoNoParseadoRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.conciliacion.entidades import CorreoNoParseado
from garay.dominio.puertos.repositorios import CorreoNoParseadoRepository
from garay.infraestructura.persistencia.modelos import CorreoNoParseadoModel


def _to_orm(correo: CorreoNoParseado) -> CorreoNoParseadoModel:
    return CorreoNoParseadoModel(
        id=correo.id,
        banco=correo.banco,
        direccion=correo.direccion,
        referencia=correo.referencia,
        asunto=correo.asunto,
        correo_origen=correo.correo_origen,
        cuerpo_texto=correo.cuerpo_texto,
        cuerpo_html=correo.cuerpo_html,
        error_parseo=correo.error_parseo,
        fecha_recibido=correo.fecha_recibido,
        procesado=correo.procesado,
        intentos=correo.intentos,
        error_ultimo=correo.error_ultimo,
    )


def _to_domain(m: CorreoNoParseadoModel) -> CorreoNoParseado:
    return CorreoNoParseado(
        id=m.id,
        banco=m.banco,
        direccion=m.direccion,
        referencia=m.referencia,
        asunto=m.asunto,
        correo_origen=m.correo_origen,
        cuerpo_texto=m.cuerpo_texto,
        cuerpo_html=m.cuerpo_html,
        error_parseo=m.error_parseo,
        fecha_recibido=m.fecha_recibido,
        procesado=m.procesado,
        intentos=m.intentos,
        error_ultimo=m.error_ultimo,
    )


class SQLACorreoNoParseadoRepository(CorreoNoParseadoRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, correo: CorreoNoParseado) -> None:
        # add() (not merge()) so a duplicate `referencia` always takes the INSERT
        # path and raises IntegrityError — the route relies on that to detect and
        # skip an already-quarantined email instead of silently overwriting it.
        with self._sf.begin() as session:
            session.add(_to_orm(correo))

    def existe_referencia(self, referencia: str) -> bool:
        with self._sf.begin() as session:
            stmt = (
                select(CorreoNoParseadoModel.id)
                .where(CorreoNoParseadoModel.referencia == referencia)
                .limit(1)
            )
            result = session.execute(stmt).scalar_one_or_none()
            return result is not None

    def listar_pendientes(self, max_intentos: int) -> list[CorreoNoParseado]:
        with self._sf.begin() as session:
            stmt = select(CorreoNoParseadoModel).where(
                CorreoNoParseadoModel.procesado == False,  # noqa: E712
                CorreoNoParseadoModel.intentos < max_intentos,
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_domain(r) for r in rows]

    def marcar_procesado(self, id: uuid.UUID) -> None:
        with self._sf.begin() as session:
            m = session.get(CorreoNoParseadoModel, id)
            if m is not None:
                m.procesado = True

    def registrar_intento_fallido(self, id: uuid.UUID, error: str) -> None:
        with self._sf.begin() as session:
            m = session.get(CorreoNoParseadoModel, id)
            if m is not None:
                m.intentos += 1
                m.error_ultimo = error
