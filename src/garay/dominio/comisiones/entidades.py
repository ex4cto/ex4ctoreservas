"""Entidades persistibles del modulo comisiones."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from garay.dominio.comisiones.valor_objetos import DesgloseComision


@dataclass(eq=False)
class ComisionRegistrada:
    """Registro persistible del desglose de comision asociado a una venta (1:1)."""

    venta_id: uuid.UUID  # PK — mismo ID que la Venta
    desglose: DesgloseComision
    fecha: datetime.date

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ComisionRegistrada) and self.venta_id == other.venta_id

    def __hash__(self) -> int:
        return hash(self.venta_id)
