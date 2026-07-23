from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal

from garay.dominio.comun.dinero import Dinero


@dataclass(frozen=True)
class DatosExtraidos:
    valor_venta: Dinero | None = None
    neto: Dinero | None = None
    servicio_nombre: str | None = None
    fecha: datetime.date | None = None
    confianza: Decimal = Decimal("0")
