"""SQLAlchemy implementation of CambiosPendientesRepository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.puertos.cambios_imagen import CambioPendiente, CambiosPendientesRepository
from garay.infraestructura.persistencia.modelos import CambioPendienteModel


def _to_domain(m: CambioPendienteModel) -> CambioPendiente:
    return CambioPendiente(
        id=m.id,
        descripcion=m.descripcion,
        creado_en=m.creado_en,
    )


class CambioPendienteRepositorioSqlAlchemy(CambiosPendientesRepository):
    """Persists pending catalog change records to the cambios_imagen_pendiente table."""

    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def registrar(self, descripcion: str) -> None:
        """Insert a new pending change record."""
        with self._sf.begin() as session:
            session.add(CambioPendienteModel(descripcion=descripcion))

    def listar_todos(self) -> list[CambioPendiente]:
        """Return all pending changes ordered by creado_en ASC."""
        with self._sf.begin() as session:
            stmt = select(CambioPendienteModel).order_by(CambioPendienteModel.creado_en)
            rows = session.execute(stmt).scalars().all()
            return [_to_domain(r) for r in rows]

    def limpiar(self) -> None:
        """Delete all pending change records."""
        with self._sf.begin() as session:
            session.query(CambioPendienteModel).delete()
