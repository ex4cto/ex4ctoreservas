"""Value object Dinero: dinero inmutable basado en Decimal, nunca float.

Es la base de toda la logica monetaria (comisiones, conciliacion, gastos). Rechaza
``float`` en construccion para evitar imprecision, y normaliza a 2 decimales con
redondeo ``ROUND_HALF_UP``.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import total_ordering
from typing import Final

from garay.dominio.comun.errores import ErrorDeDominio

_DOS_DECIMALES: Final = Decimal("0.01")
_CIEN: Final = Decimal("100")

MontoAceptado = int | str | Decimal
Factor = int | Decimal


class MontoInvalido(ErrorDeDominio):
    """El valor provisto no es un monto monetario valido."""


class MonedaIncompatible(ErrorDeDominio):
    """No se pueden operar importes de distinta moneda."""


@total_ordering
class Dinero:
    """Importe monetario inmutable. Igualdad y orden respetan la moneda."""

    __slots__ = ("_moneda", "_monto")

    _monto: Decimal
    _moneda: str

    def __init__(self, monto: MontoAceptado, moneda: str = "COP") -> None:
        object.__setattr__(self, "_monto", self._normalizar(monto))
        object.__setattr__(self, "_moneda", moneda)

    @staticmethod
    def _normalizar(valor: MontoAceptado) -> Decimal:
        if isinstance(valor, bool | float):
            raise MontoInvalido(
                f"No se permite float ni bool para dinero: {valor!r}. Usa int, str o Decimal."
            )
        try:
            decimal = valor if isinstance(valor, Decimal) else Decimal(valor)
        except (InvalidOperation, ValueError) as exc:
            raise MontoInvalido(f"Monto invalido: {valor!r}.") from exc
        return decimal.quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)

    @property
    def monto(self) -> Decimal:
        return self._monto

    @property
    def moneda(self) -> str:
        return self._moneda

    def __setattr__(self, nombre: str, valor: object) -> None:
        raise AttributeError("Dinero es inmutable.")

    def __delattr__(self, nombre: str) -> None:
        raise AttributeError("Dinero es inmutable.")

    def _verificar_moneda(self, otro: Dinero) -> None:
        if self._moneda != otro._moneda:
            raise MonedaIncompatible(f"Distinta moneda: {self._moneda} vs {otro._moneda}.")

    def _validar_factor(self, factor: Factor, contexto: str) -> Decimal:
        if isinstance(factor, bool | float):
            raise MontoInvalido(f"El {contexto} debe ser int o Decimal, no float ni bool.")
        return factor if isinstance(factor, Decimal) else Decimal(factor)

    def __add__(self, otro: Dinero) -> Dinero:
        self._verificar_moneda(otro)
        return Dinero(self._monto + otro._monto, self._moneda)

    def __sub__(self, otro: Dinero) -> Dinero:
        self._verificar_moneda(otro)
        return Dinero(self._monto - otro._monto, self._moneda)

    def __mul__(self, factor: Factor) -> Dinero:
        multiplicador = self._validar_factor(factor, "factor")
        return Dinero(self._monto * multiplicador, self._moneda)

    def aplicar_porcentaje(self, porcentaje: Factor) -> Dinero:
        """Devuelve el ``porcentaje`` (0-100) de este importe, redondeado."""
        valor = self._validar_factor(porcentaje, "porcentaje")
        return Dinero(self._monto * valor / _CIEN, self._moneda)

    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, Dinero):
            return NotImplemented
        return self._monto == otro._monto and self._moneda == otro._moneda

    def __lt__(self, otro: Dinero) -> bool:
        if not isinstance(otro, Dinero):
            return NotImplemented
        self._verificar_moneda(otro)
        return self._monto < otro._monto

    def __hash__(self) -> int:
        return hash((self._monto, self._moneda))

    def __repr__(self) -> str:
        return f"Dinero({str(self._monto)!r}, {self._moneda!r})"

    def __str__(self) -> str:
        return f"{self._monto} {self._moneda}"
