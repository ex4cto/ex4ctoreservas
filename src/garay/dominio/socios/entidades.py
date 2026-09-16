"""Domain entities for socios (partners) — divisiones de socios feature."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal

from garay.dominio.comun.dinero import Dinero


@dataclass(frozen=True)
class SocioConfig:
    """Editable configuration for each partner (socio)."""

    nombre: str  # "empresa" | "garay" | "ryan"
    porcentaje: Decimal  # e.g. 50, 25, 25
    telegram_id: int | None  # for private messages; None if not configured


@dataclass(eq=False)
class PagoSocio:
    """Record of each manual partner payment (liquidacion)."""

    id: uuid.UUID
    nombre_socio: str  # "garay" | "ryan" | "empresa"
    monto: Dinero
    fecha: datetime.date
    tipo: str  # "total" | "parcial"
    nota: str | None
    registrado_en: datetime.datetime

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PagoSocio) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
