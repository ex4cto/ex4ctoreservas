"""Entidades del modulo clientes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from garay.dominio.clientes.errores import NombreClienteVacio
from garay.dominio.comun.tipos import TipoCliente


class CampoCliente(StrEnum):
    """Campos editables de un cliente. El valor coincide con el atributo de Cliente."""

    NOMBRE = "nombre"
    TELEFONO = "telefono"
    EMAIL = "email"
    IDENTIFICACION = "identificacion"
    HOTEL = "hotel"
    NUMERO_HABITACION = "numero_habitacion"


@dataclass(eq=False)
class Cliente:
    """Representa a un cliente del sistema Garay."""

    id: uuid.UUID
    nombre: str
    tipo: TipoCliente
    telefono: str | None = None
    hotel: str | None = None
    numero_habitacion: str | None = None
    email: str | None = None
    identificacion: str | None = None
    tipo_identificacion: str | None = None

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise NombreClienteVacio("El nombre del cliente no puede estar vacio.")

    def actualizar_campo(self, campo: CampoCliente, valor: str) -> None:
        """Update one editable field. `nombre` must not be blank; the value is stripped.

        The enum value equals the target attribute name, so the assignment is
        driven by the enum itself.
        """
        valor_limpio = valor.strip()
        if campo == CampoCliente.NOMBRE and not valor_limpio:
            raise NombreClienteVacio("El nombre del cliente no puede estar vacio.")
        setattr(self, campo.value, valor_limpio)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Cliente) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
