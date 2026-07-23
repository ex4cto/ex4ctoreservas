from __future__ import annotations

from abc import ABC, abstractmethod

from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.ventas.entidades import Venta


class MotorComisionesBase(ABC):
    @abstractmethod
    def calcular(self, venta: Venta, punto: PuntoDeVenta | None) -> DesgloseComision: ...
