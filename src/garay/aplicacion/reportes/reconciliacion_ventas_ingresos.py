"""ReconciliacionVentasIngresosService — cruza la parte-agencia esperada vs el banco.

Compara la suma de la comision de agencia (lo que le toca a Garay segun las ventas)
contra los ingresos bancarios reales del mes. La diferencia chica (~2%) valida que
los datos cierran.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ComisionRegistradaRepository,
    IngresoRepository,
    VentaRepository,
)


@dataclass(frozen=True)
class ReconciliacionVentasIngresos:
    mes: int
    año: int
    total_agencia_esperada: Dinero
    total_ingresos_banco: Dinero
    diferencia: Dinero
    porcentaje_desviacion: Decimal


class ReconciliacionVentasIngresosService:
    def __init__(
        self,
        ventas: VentaRepository,
        comisiones: ComisionRegistradaRepository,
        ingresos: IngresoRepository,
    ) -> None:
        self._ventas = ventas
        self._comisiones = comisiones
        self._ingresos = ingresos

    def ejecutar(self, mes: int, año: int) -> ReconciliacionVentasIngresos:
        desde = date(año, mes, 1)
        hasta = date(año, mes, calendar.monthrange(año, mes)[1])

        ventas = self._ventas.listar_por_periodo(desde, hasta)
        comisiones = self._comisiones.listar_por_venta_ids([v.id for v in ventas])
        agencia = sum((c.desglose.agencia for c in comisiones), start=Dinero(0))

        ingresos = self._ingresos.listar_por_periodo(desde, hasta)
        banco = sum((i.monto for i in ingresos), start=Dinero(0))

        diferencia = banco - agencia
        desviacion = (
            diferencia.monto / agencia.monto * Decimal("100")
            if agencia.monto
            else Decimal("0")
        )
        return ReconciliacionVentasIngresos(
            mes=mes,
            año=año,
            total_agencia_esperada=agencia,
            total_ingresos_banco=banco,
            diferencia=diferencia,
            porcentaje_desviacion=desviacion,
        )
