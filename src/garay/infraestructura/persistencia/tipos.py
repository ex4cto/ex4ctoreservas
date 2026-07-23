"""Tipos SQLAlchemy propios del dominio.

``TipoDinero`` traduce entre la columna ``NUMERIC`` de la base y el value object
``Dinero``. Persiste solo el monto (la moneda del sistema es unica: COP). Si en el
futuro se necesitara multi-moneda, habria que pasar a un tipo compuesto (dos columnas).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from garay.dominio.comun.dinero import Dinero

# Precision amplia para montos grandes en COP; escala 2 por el redondeo de Dinero.
_NUMERIC = Numeric(precision=18, scale=2)


class TipoDinero(TypeDecorator[Dinero]):
    """Mapea ``Dinero`` <-> ``NUMERIC``. La moneda se fija por columna (default COP)."""

    impl = _NUMERIC
    cache_ok = True

    def __init__(self, moneda: str = "COP") -> None:
        super().__init__()
        self.moneda = moneda

    def process_bind_param(self, value: Dinero | None, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        return value.monto

    def process_result_value(self, value: Decimal | None, dialect: Dialect) -> Dinero | None:
        if value is None:
            return None
        return Dinero(value, self.moneda)
