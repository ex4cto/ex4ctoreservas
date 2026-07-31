"""WaterfallVentasService — cascada bruto -> neto -> margen -> agencia del mes.

Estandariza el bloque de TOTALES que antes se calculaba a mano en los scripts:
valor_bruto - costo_neto = margen; margen - comisiones = ganancia_agencia.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import ComisionRegistradaRepository, VentaRepository


@dataclass(frozen=True)
class WaterfallVentas:
    mes: int
    año: int
    valor_bruto: Dinero
    costo_neto: Dinero
    margen: Dinero
    comisiones: Dinero
    ganancia_agencia: Dinero


class WaterfallVentasService:
    def __init__(
        self, ventas: VentaRepository, comisiones: ComisionRegistradaRepository
    ) -> None:
        self._ventas = ventas
        self._comisiones = comisiones

    def ejecutar(self, mes: int, año: int) -> WaterfallVentas:
        desde = date(año, mes, 1)
        hasta = date(año, mes, calendar.monthrange(año, mes)[1])
        ventas = self._ventas.listar_por_periodo(desde, hasta)

        valor = sum((v.valor_venta for v in ventas), start=Dinero(0))
        neto = sum((v.neto for v in ventas), start=Dinero(0))
        margen = valor - neto

        comisiones = self._comisiones.listar_por_venta_ids([v.id for v in ventas])
        agencia = sum((c.desglose.agencia for c in comisiones), start=Dinero(0))

        return WaterfallVentas(
            mes=mes,
            año=año,
            valor_bruto=valor,
            costo_neto=neto,
            margen=margen,
            comisiones=margen - agencia,
            ganancia_agencia=agencia,
        )
