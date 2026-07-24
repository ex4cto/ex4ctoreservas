"""Entidades del modulo servicios."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from garay.dominio.servicios.errores import NombreServicioVacio, NumeroServicioInvalido


@dataclass(eq=False)
class Servicio:
    """Representa un servicio turistico ofrecido por Garay Tours."""

    id: uuid.UUID
    numero: int
    nombre: str
    descripcion: str = field(default="")
    activo: bool = field(default=True)

    def __post_init__(self) -> None:
        if self.numero < 1:
            raise NumeroServicioInvalido("El numero del servicio debe ser mayor a cero.")
        if not self.nombre.strip():
            raise NombreServicioVacio("El nombre del servicio no puede estar vacio.")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Servicio) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
