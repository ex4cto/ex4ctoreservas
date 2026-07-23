from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.errores import (
    DescripcionEgresoVacia,
    MontoInvalido,
    ReferenciaIngresoVacia,
)
from garay.dominio.conciliacion.tipos import CategoriaEgreso, EstadoConciliacion, TipoEgreso

_CERO = Dinero(0)


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
    categoria: CategoriaEgreso
    tipo: TipoEgreso = field(default=TipoEgreso.MANUAL)

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
class Conciliacion:
    id: uuid.UUID
    ingreso_id: uuid.UUID
    venta_id: uuid.UUID | None = field(default=None)
    estado: EstadoConciliacion = field(default=EstadoConciliacion.PENDIENTE)
    notas: str = field(default="")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Conciliacion) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
