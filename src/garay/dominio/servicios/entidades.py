"""Entidades del modulo servicios."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from garay.dominio.servicios.errores import NombreServicioVacio


@dataclass(eq=False)
class Servicio:
    """Representa un servicio turistico ofrecido por Garay Tours."""

    id: uuid.UUID
    nombre: str
    descripcion: str = field(default="")

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise NombreServicioVacio("El nombre del servicio no puede estar vacio.")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Servicio) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
