"""Entidades del modulo puntos de venta."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from garay.dominio.puntos_venta.errores import NombrePuntoVacio, PorcentajeCapaInvalido


@dataclass(eq=False)
class PuntoDeVenta:
    """Representa un punto de venta con su porcentaje de capa asignado."""

    id: uuid.UUID
    nombre: str
    porcentaje_capa: Decimal

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise NombrePuntoVacio("El nombre del punto de venta no puede estar vacio.")
        if self.porcentaje_capa <= Decimal(0) or self.porcentaje_capa > Decimal(100):
            raise PorcentajeCapaInvalido(
                f"El porcentaje de capa debe estar entre 1 y 100. Recibido: {self.porcentaje_capa}."
            )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PuntoDeVenta) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
