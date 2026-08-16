"""SQLAlchemy adapter: ContadorFacturasEnviadas implementation.

Counts FacturaModel rows with estado_envio = 'ENVIADO' within
the requested date scope.  No domain objects are constructed — the
queries return plain integer counts.
"""

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.puertos.contador_facturas import ContadorFacturasEnviadas
from garay.infraestructura.persistencia.modelos import FacturaModel

_ENVIADO = "ENVIADO"


class ContadorFacturasSQLAlchemy(ContadorFacturasEnviadas):
    """SQLAlchemy implementation of ContadorFacturasEnviadas.

    Args:
        sf: A sessionmaker bound to the application engine.
    """

    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def contar_mes_a_la_fecha(self, hasta: datetime.date) -> int:
        """Count ENVIADO invoices in the calendar month of *hasta*, up to *hasta* inclusive.

        Window: [first_day_of_month(hasta), hasta].
        """
        primer_dia = hasta.replace(day=1)
        with self._sf.begin() as session:
            stmt = select(func.count()).select_from(FacturaModel).where(
                FacturaModel.estado_envio == _ENVIADO,
                FacturaModel.fecha_emision >= primer_dia,
                FacturaModel.fecha_emision <= hasta,
            )
            result: int | None = session.execute(stmt).scalar()
            return result if result is not None else 0

    def contar_dia(self, dia: datetime.date) -> int:
        """Count ENVIADO invoices with fecha_emision == *dia*."""
        with self._sf.begin() as session:
            stmt = select(func.count()).select_from(FacturaModel).where(
                FacturaModel.estado_envio == _ENVIADO,
                FacturaModel.fecha_emision == dia,
            )
            result: int | None = session.execute(stmt).scalar()
            return result if result is not None else 0
