"""Entidades del modulo freelancers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from garay.dominio.freelancers.errores import NombreFreelancerVacio


@dataclass(eq=False)
class Freelancer:
    """Representa un vendedor/guia independiente que opera con Garay Tours."""

    id: uuid.UUID
    nombre: str
    activo: bool = field(default=True)
    telegram_user_id: int | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise NombreFreelancerVacio("El nombre del freelancer no puede estar vacio.")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Freelancer) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
