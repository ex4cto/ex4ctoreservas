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
    permite_ninos: bool = field(default=True)
    categoria: str = field(default="")
    horarios: list[str] = field(default_factory=list)

    netos_por_horario: dict[str, Decimal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.horarios = sorted(self.horarios)
        if self.numero < 1:
            raise NumeroServicioInvalido("El numero del servicio debe ser mayor a cero.")
        if not self.nombre.strip():
            raise NombreServicioVacio("El nombre del servicio no puede estar vacio.")
        for key, val in self.netos_por_horario.items():
            if not isinstance(val, Decimal):
                raise TypeError(
                    f"netos_por_horario['{key}'] must be Decimal, got {type(val).__name__}"
                )

    def neto_para_horario(self, horario: str | None) -> Decimal | None:
        """Return the net cost for the given departure time.

        Resolution order:
        1. If horario is non-None and present in netos_por_horario → return that value.
        2. Otherwise return precio_neto_adulto (may be None).
        """
        if horario is not None and horario in self.netos_por_horario:
            return self.netos_por_horario[horario]
        return self.precio_neto_adulto

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Servicio) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
