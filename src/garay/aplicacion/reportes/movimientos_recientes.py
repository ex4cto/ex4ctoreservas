"""Application service: recent ingresos and egresos summary."""

from __future__ import annotations

from dataclasses import dataclass

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso, Ingreso
from garay.dominio.puertos.repositorios import EgresoRepository, IngresoRepository


@dataclass(frozen=True)
class MovimientosRecientes:
    """Snapshot of ingresos and egresos received within a recent time window."""

    ingresos: tuple[Ingreso, ...]
    egresos: tuple[Egreso, ...]
    total_ingresos: Dinero
    total_egresos: Dinero


class MovimientosRecientesService:
    def __init__(
        self,
        ingresos_repo: IngresoRepository,
        egresos_repo: EgresoRepository,
    ) -> None:
        self._ingresos = ingresos_repo
        self._egresos = egresos_repo

    def ejecutar(self, horas: int = 24) -> MovimientosRecientes:
        """Return ingresos and egresos received within the last *horas* hours."""
        minutos = horas * 60
        ingresos = self._ingresos.listar_recientes(minutos)
        egresos = self._egresos.listar_recientes(minutos)

        total_ingresos = sum((i.monto for i in ingresos), start=Dinero(0))
        total_egresos = sum((e.monto for e in egresos), start=Dinero(0))

        return MovimientosRecientes(
            ingresos=tuple(ingresos),
            egresos=tuple(egresos),
            total_ingresos=total_ingresos,
            total_egresos=total_egresos,
        )
