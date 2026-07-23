from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.ventas.entidades import Venta


class MotorComisionesBase(ABC):
    @abstractmethod
    def calcular(
        self,
        venta: Venta,
        reglas: ReglasComision,
        punto: PuntoDeVenta | None,
        porcentaje_referido: Decimal = Decimal("0"),
    ) -> DesgloseComision: ...
