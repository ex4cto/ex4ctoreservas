from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.puntos_venta.entidades import PuntoDeVenta

_CERO = Decimal("0")


@dataclass(frozen=True)
class SnapshotReglas:
    """Snapshot inmutable de ReglasComision en el momento de registrar la venta.

    Se almacena junto a la venta para que cambios futuros en las reglas no
    alteren calculos historicos.
    """

    tipo_cliente: TipoCliente
    porcentaje_vendedor: Decimal
    porcentaje_cerrador: Decimal
    porcentaje_referido_maximo: Decimal
    porcentaje_capa_punto: Decimal

    @classmethod
    def desde_reglas(
        cls,
        reglas: ReglasComision,
        punto: PuntoDeVenta | None,
    ) -> SnapshotReglas:
        return cls(
            tipo_cliente=reglas.tipo_cliente,
            porcentaje_vendedor=reglas.porcentaje_vendedor,
            porcentaje_cerrador=reglas.porcentaje_cerrador,
            porcentaje_referido_maximo=reglas.porcentaje_referido_maximo,
            porcentaje_capa_punto=punto.porcentaje_capa if punto else _CERO,
        )
