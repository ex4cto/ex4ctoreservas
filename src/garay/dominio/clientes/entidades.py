"""Entidades del modulo clientes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from garay.dominio.clientes.errores import NombreClienteVacio
from garay.dominio.comun.tipos import TipoCliente


@dataclass(eq=False)
class Cliente:
    """Representa a un cliente del sistema Garay."""

    id: uuid.UUID
    nombre: str
    tipo: TipoCliente
    telefono: str | None = None
    hotel: str | None = None
    numero_habitacion: str | None = None

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise NombreClienteVacio("El nombre del cliente no puede estar vacio.")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Cliente) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
