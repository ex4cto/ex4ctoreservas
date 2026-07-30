from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.errores import (
    DescripcionEgresoVacia,
    MontoInvalido,
    ReferenciaIngresoVacia,
)
from garay.dominio.conciliacion.tipos import EstadoConciliacion, TipoEgreso
from garay.dominio.ventas.entidades import Venta

_CERO = Dinero(0)


@dataclass
class CategoriaEgreso:
    """Categoria de egreso gestionada en base de datos (no enum fijo)."""

    nombre: str
    descripcion: str
    activo: bool
    orden: int


@dataclass(eq=False)
class Ingreso:
    id: uuid.UUID
    banco: str
    monto: Dinero
    fecha: datetime.date
    referencia: str
    remitente: str | None = field(default=None)
    clasificado: bool = field(default=False)
    venta_id: uuid.UUID | None = field(default=None)
    # Timestamp of receipt (UTC). None for legacy records created before this field existed.
    fecha_recibido: datetime.datetime | None = field(default=None)
    # Email address of the original sender (from the forwarded email payload).
    correo_origen: str | None = field(default=None)
    # True if the email was a forward (Fwd:/Fw:/Rv: prefix or forwarded-message body).
    reenviado: bool = field(default=False)

    def __post_init__(self) -> None:
        if not self.referencia.strip():
            raise ReferenciaIngresoVacia("La referencia del ingreso no puede estar vacia.")
        if self.monto <= _CERO:
            raise MontoInvalido("El monto del ingreso debe ser mayor que cero.")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Ingreso) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(eq=False)
class Egreso:
    id: uuid.UUID
    descripcion: str
    monto: Dinero
    fecha: datetime.date
    categoria: str
    tipo: TipoEgreso = field(default=TipoEgreso.MANUAL)
    # Unique message ID used as idempotency key for webhook-originated egresos.
    referencia: str | None = field(default=None)
    # UTC timestamp of receipt. None for manually-created records.
    fecha_recibido: datetime.datetime | None = field(default=None)
    # Email address of the original sender (from the forwarded email payload).
    correo_origen: str | None = field(default=None)
    # True if the email was a forward (Fwd:/Fw:/Rv: prefix or forwarded-message body).
    reenviado: bool = field(default=False)

    def __post_init__(self) -> None:
        if not self.descripcion.strip():
            raise DescripcionEgresoVacia("La descripcion del egreso no puede estar vacia.")
        if self.monto <= _CERO:
            raise MontoInvalido("El monto del egreso debe ser mayor que cero.")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Egreso) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(eq=False)
class GastoRecurrente:
    """Gasto fijo que se genera periodicamente (por ejemplo: arriendo mensual)."""

    id: uuid.UUID
    nombre: str
    monto: Dinero
    categoria: str
    dia_mes: int  # 1-28
    activo: bool = field(default=True)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GastoRecurrente) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(eq=False)
class Conciliacion:
    id: uuid.UUID
    ingreso_id: uuid.UUID
    venta_id: uuid.UUID | None = field(default=None)
    estado: EstadoConciliacion = field(default=EstadoConciliacion.PENDIENTE)
    notas: str = field(default="")
    score: Decimal | None = field(default=None)
    confianza: Decimal | None = field(default=None)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Conciliacion) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(eq=False)
class CandidatoMatch:
    """Venta candidata a ser emparejada con un ingreso, con su score calculado."""

    venta: Venta
    score: Decimal          # 0.0 - 1.0
    diferencia_monto: Dinero  # diferencia absoluta en unidades monetarias

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CandidatoMatch) and self.venta == other.venta

    def __hash__(self) -> int:
        return hash(self.venta.id)


@dataclass(frozen=True)
class ResultadoConciliacion:
    """Resumen del resultado de ejecutar el servicio de conciliacion."""

    matcheados: int
    sin_match: int
    pendientes: int
