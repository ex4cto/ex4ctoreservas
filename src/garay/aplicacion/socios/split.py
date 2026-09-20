"""DTOs for partner split summary — application layer."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Period-scoped DTOs (no pendiente — PagoSocioRepository has no date filter)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResumenSocioPeriodo:
    """Per-partner share for a date-range query.

    No ``pendiente`` field: the period view reflects only accrued agencia,
    not outstanding payments.
    """

    nombre: str
    porcentaje: Decimal
    acumulado: Dinero


@dataclass(frozen=True)
class ResumenFreelancerPeriodo:
    """Per-freelancer commission total for a date range."""

    nombre: str
    comision: Dinero


@dataclass(frozen=True)
class ResumenVentaDetalle:
    """Per-sale breakdown for drill-down view in /resumen_divisiones."""

    venta_id: uuid.UUID
    fecha: datetime.date
    vendedor_nombre: str | None
    cerrador_nombre: str | None
    valor_bruto: Dinero
    desglose_vendedor: Dinero
    desglose_cerrador: Dinero
    desglose_punto: Dinero
    desglose_agencia: Dinero
    split_socios: tuple[ResumenSocioPeriodo, ...]


@dataclass(frozen=True)
class ResumenSplitPeriodo:
    """Aggregate split result for a [desde, hasta] date range."""

    por_socio: tuple[ResumenSocioPeriodo, ...]  # order: empresa → garay → ryan
    total_agencia: Dinero
    total_bruto: Dinero
    total_comisiones_freelancer: Dinero
    ventas_count: int
    ventas_detalle: tuple[ResumenVentaDetalle, ...] = field(default_factory=tuple)
    por_freelancer: tuple[ResumenFreelancerPeriodo, ...] = field(default_factory=tuple)
