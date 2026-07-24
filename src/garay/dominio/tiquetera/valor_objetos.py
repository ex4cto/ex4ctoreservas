from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from garay.dominio.comun.dinero import Dinero


@dataclass(frozen=True)
class DatosExtraidos:
    """Datos extraídos de una foto de tiquetera por el ExtractorIA."""

    # Financial
    valor_venta: Dinero | None = None
    neto: Dinero | None = None
    abono: Dinero | None = None
    # Client
    nombre_cliente: str | None = None
    telefono: str | None = None
    cliente_hotel: str | None = None
    numero_habitacion: str | None = None
    # Service
    servicio_nombre: str | None = None
    destinos: tuple[str, ...] = field(default_factory=tuple)
    # Logistics
    fecha_salida: datetime.datetime | None = None
    adultos: int | None = None
    ninos: int | None = None
    numero_ticket: int | None = None
    # Metadata
    confianza: Decimal = Decimal("0")
