"""ContextoCotizacion — data-transfer object for the quote flow.

Not related to ContextoVenta. Dedicated DTO with no inheritance.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal


@dataclass
class ContextoCotizacion:
    """Carries all data collected across the cotizacion conversation flow."""

    cliente_nombre: str | None = None
    cliente_email: str | None = None
    destinos_numeros: list[int] = field(default_factory=list)
    destinos_nombres: list[str] = field(default_factory=list)
    familia_seleccionada: str | None = None
    fecha_salida: datetime.datetime | None = None
    adultos: int | None = None
    ninos: int = 0
    factura_idioma: str = "es"  # "es" | "en"; invalid values fall back to "es"
    precio_adulto: Decimal | None = None  # populated from Servicio.precio_neto_adulto
    precio_nino: Decimal | None = None    # populated from Servicio.precio_neto_nino
    vendedor_nombre: str | None = None    # generating user's display name
    sin_hotel: bool = True

    def __post_init__(self) -> None:
        for nombre, val in (
            ("precio_adulto", self.precio_adulto),
            ("precio_nino", self.precio_nino),
        ):
            if val is not None and not isinstance(val, Decimal):
                raise TypeError(
                    f"{nombre} must be Decimal, got {type(val).__name__}"
                )

    @property
    def valor_total(self) -> Decimal:
        """Calculate total price: adultos x precio_adulto + ninos x precio_nino.

        None prices are treated as Decimal("0") (graceful degradation per SC-B03/B04).
        Result is quantized to 0 decimal places (COP whole pesos).
        """
        pa = self.precio_adulto or Decimal("0")
        pn = self.precio_nino or Decimal("0")
        total = pa * (self.adultos or 0) + pn * self.ninos
        return total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
