"""Entidades del modulo servicios."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from garay.dominio.servicios.errores import NombreServicioVacio, NumeroServicioInvalido


@dataclass(eq=False)
class Servicio:
    """Representa un servicio turistico ofrecido por Garay Tours."""

    id: uuid.UUID
    numero: int
    nombre: str
    descripcion: str = field(default="")
    activo: bool = field(default=True)
    precio_neto_adulto: Decimal | None = field(default=None)
    precio_neto_nino: Decimal | None = field(default=None)
    categoria: str = field(default="")
    horarios: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.horarios = sorted(self.horarios)
        if self.numero < 1:
            raise NumeroServicioInvalido("El numero del servicio debe ser mayor a cero.")
        if not self.nombre.strip():
            raise NombreServicioVacio("El nombre del servicio no puede estar vacio.")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Servicio) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
