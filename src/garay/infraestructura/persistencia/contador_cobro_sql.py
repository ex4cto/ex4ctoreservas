"""SQLAlchemy adapter: atomic consecutive counter for cuentas de cobro.

Each call to siguiente_numero() increments the counter for the given
document type within a single transaction, guaranteeing no gaps from
concurrent writes.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from garay.infraestructura.persistencia.modelos import ContadorDocumentoModel


class ContadorDocumentoSQLAlchemy:
    """Atomic consecutive-number counter backed by the contadores_documento table.

    Args:
        sf: A sessionmaker bound to the application engine.
    """

    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def siguiente_numero(self, tipo: str) -> int:
        """Return the next consecutive number for *tipo*, incrementing atomically.

        - If no row exists for *tipo*: inserts with ultimo_numero=1, returns 1.
        - Otherwise: increments ultimo_numero by 1 and returns the new value.

        The entire operation runs inside a single DB transaction.
        """
        with self._sf.begin() as session:
            row = session.get(ContadorDocumentoModel, tipo)
            if row is None:
                nuevo = ContadorDocumentoModel(tipo=tipo, ultimo_numero=1)
                session.add(nuevo)
                return 1
            row.ultimo_numero += 1
            return row.ultimo_numero
