"""Servicio de aplicacion para ejecutar el proceso de conciliacion de ingresos.

Orquesta IngresoRepository, VentaRepository, ConciliacionRepository y el
MotorConciliacionBase para producir un ResultadoConciliacion.

Optimizacion clave: una sola consulta al repo de ventas para el rango
unificado de fechas — evita el problema N+1.
"""

from __future__ import annotations

from datetime import timedelta

from garay.dominio.conciliacion.entidades import ResultadoConciliacion
from garay.dominio.conciliacion.servicio import MotorConciliacionBase
from garay.dominio.conciliacion.tipos import EstadoConciliacion
from garay.dominio.puertos.repositorios import (
    ConciliacionRepository,
    IngresoRepository,
    VentaRepository,
)


class ConciliarIngresosService:
    """Caso de uso: conciliar todos los ingresos sin clasificar contra ventas existentes."""

    def __init__(
        self,
        *,
        ingresos: IngresoRepository,
        ventas: VentaRepository,
        conciliaciones: ConciliacionRepository,
        motor: MotorConciliacionBase,
        ventana_dias: int,
    ) -> None:
        self._ingresos = ingresos
        self._ventas = ventas
        self._conciliaciones = conciliaciones
        self._motor = motor
        self._ventana_dias = ventana_dias

    def ejecutar(self) -> ResultadoConciliacion:
        """Procesa todos los ingresos sin clasificar y devuelve el resumen."""
        sin_clasificar = self._ingresos.listar_sin_clasificar()
        if not sin_clasificar:
            return ResultadoConciliacion(matcheados=0, sin_match=0, pendientes=0)

        ya_procesados = set(self._conciliaciones.listar_ingreso_ids_procesados())
        pendientes = [i for i in sin_clasificar if i.id not in ya_procesados]

        if not pendientes:
            return ResultadoConciliacion(matcheados=0, sin_match=0, pendientes=0)

        # Una sola query para el rango unificado — evita N+1
        fechas = [i.fecha for i in pendientes]
        desde = min(fechas) - timedelta(days=self._ventana_dias)
        hasta = max(fechas) + timedelta(days=self._ventana_dias)
        todas_ventas = self._ventas.listar_por_periodo(desde, hasta)

        matcheados = 0
        sin_match = 0
        mantenidos = 0

        for ingreso in pendientes:
            candidatas = [
                v for v in todas_ventas
                if abs((v.fecha - ingreso.fecha).days) <= self._ventana_dias
            ]
            conciliacion = self._motor.conciliar(ingreso, candidatas)
            self._conciliaciones.guardar(conciliacion)

            if conciliacion.estado == EstadoConciliacion.MATCHEADO:
                matcheados += 1
            elif conciliacion.estado == EstadoConciliacion.SIN_MATCH:
                sin_match += 1
            else:
                mantenidos += 1

        return ResultadoConciliacion(
            matcheados=matcheados,
            sin_match=sin_match,
            pendientes=mantenidos,
        )
