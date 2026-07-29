"""FlujoCajaService — monthly cash flow summary for dashboard."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.tipos import EstadoConciliacion
from garay.dominio.puertos.repositorios import (
    ConciliacionRepository,
    EgresoRepository,
    IngresoRepository,
)


@dataclass(frozen=True)
class FlujoCaja:
    mes: int
    año: int
    total_ingresos: Dinero
    total_egresos: Dinero
    balance: Dinero
    ingresos_conciliados: int
    ingresos_pendientes: int
    egresos_por_categoria: tuple[tuple[str, Dinero], ...]


class FlujoCajaService:
    def __init__(
        self,
        ingresos: IngresoRepository,
        egresos: EgresoRepository,
        conciliaciones: ConciliacionRepository,
    ) -> None:
        self._ingresos = ingresos
        self._egresos = egresos
        self._conciliaciones = conciliaciones

    def ejecutar(self, mes: int, año: int) -> FlujoCaja:
        desde = date(año, mes, 1)
        hasta = date(año, mes, calendar.monthrange(año, mes)[1])

        ingresos = self._ingresos.listar_por_periodo(desde, hasta)
        egresos = self._egresos.listar_por_periodo(desde, hasta)
        conciliaciones = self._conciliaciones.listar_por_periodo(desde, hasta)

        total_ingresos = sum((i.monto for i in ingresos), start=Dinero(0))
        total_egresos = sum((e.monto for e in egresos), start=Dinero(0))
        balance = total_ingresos - total_egresos

        conciliados = sum(
            1 for c in conciliaciones if c.estado == EstadoConciliacion.MATCHEADO
        )
        pendientes = sum(
            1
            for c in conciliaciones
            if c.estado in {EstadoConciliacion.PENDIENTE, EstadoConciliacion.SIN_MATCH}
        )

        por_cat: dict[str, Dinero] = {}
        for e in egresos:
            por_cat[e.categoria] = por_cat.get(e.categoria, Dinero(0)) + e.monto

        return FlujoCaja(
            mes=mes,
            año=año,
            total_ingresos=total_ingresos,
            total_egresos=total_egresos,
            balance=balance,
            ingresos_conciliados=conciliados,
            ingresos_pendientes=pendientes,
            egresos_por_categoria=tuple(sorted(por_cat.items())),
        )
