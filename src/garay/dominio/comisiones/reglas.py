from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from garay.dominio.comisiones.errores import PorcentajeInvalidoRegla
from garay.dominio.comun.tipos import TipoCliente

_CIEN = Decimal("100")
_CERO = Decimal("0")
_TECHO_REFERIDO = Decimal("10")


@dataclass(eq=False)
class ReglasComision:
    """Config entity: splits por TipoCliente. Vive en DB, se lee en runtime."""

    id: uuid.UUID
    tipo_cliente: TipoCliente
    porcentaje_vendedor: Decimal
    porcentaje_cerrador: Decimal
    porcentaje_referido_maximo: Decimal

    def __post_init__(self) -> None:
        if self.porcentaje_vendedor < _CERO or self.porcentaje_cerrador < _CERO:
            raise PorcentajeInvalidoRegla(
                "Los porcentajes de vendedor y cerrador deben ser >= 0. "
                f"Recibido: vendedor={self.porcentaje_vendedor}, "
                f"cerrador={self.porcentaje_cerrador}."
            )
        if self.porcentaje_vendedor + self.porcentaje_cerrador > _CIEN:
            raise PorcentajeInvalidoRegla(
                "La suma de porcentaje_vendedor y porcentaje_cerrador no puede superar 100. "
                f"Recibido: {self.porcentaje_vendedor + self.porcentaje_cerrador}."
            )
        if not (_CERO <= self.porcentaje_referido_maximo <= _TECHO_REFERIDO):
            raise PorcentajeInvalidoRegla(
                f"El referido no puede superar el {_TECHO_REFERIDO}%. "
                f"Recibido: {self.porcentaje_referido_maximo}."
            )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ReglasComision) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
