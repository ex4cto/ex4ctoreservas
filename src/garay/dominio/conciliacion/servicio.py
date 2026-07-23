from __future__ import annotations

from abc import ABC, abstractmethod

from garay.dominio.conciliacion.entidades import Conciliacion, Ingreso
from garay.dominio.ventas.entidades import Venta


class MotorConciliacionBase(ABC):
    @abstractmethod
    def conciliar(
        self,
        ingreso: Ingreso,
        ventas_candidatas: list[Venta],
    ) -> Conciliacion: ...
