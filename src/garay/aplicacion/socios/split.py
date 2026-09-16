"""DTOs for partner split summary — application layer."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from garay.dominio.comun.dinero import Dinero


@dataclass(frozen=True)
class ResumenSocio:
    nombre: str
    porcentaje: Decimal
    acumulado: Dinero   # total earnings based on historical sales
    pagado: Dinero      # sum of PagoSocio for this partner
    pendiente: Dinero   # acumulado - pagado


@dataclass(frozen=True)
class ResumenSplitSocios:
    por_socio: tuple[ResumenSocio, ...]  # order: empresa → garay → ryan
    total_agencia: Dinero               # sum of agencia from all sales
