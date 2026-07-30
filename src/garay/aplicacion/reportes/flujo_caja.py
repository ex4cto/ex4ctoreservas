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
class ResumenBanco:
    banco: str
    cantidad: int
    monto_total: Dinero


@dataclass(frozen=True)
class ResumenEstado:
    estado: str
    cantidad: int
    monto_total: Dinero


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
    ingresos_por_banco: tuple[ResumenBanco, ...] = ()
    ingresos_por_estado: tuple[ResumenEstado, ...] = ()


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

        # ingresos_por_banco
        banco_conteo: dict[str, int] = {}
        banco_monto: dict[str, Dinero] = {}
        for i in ingresos:
            banco_conteo[i.banco] = banco_conteo.get(i.banco, 0) + 1
            banco_monto[i.banco] = banco_monto.get(i.banco, Dinero(0)) + i.monto
        ingresos_por_banco = tuple(
            ResumenBanco(banco=b, cantidad=banco_conteo[b], monto_total=banco_monto[b])
            for b in sorted(banco_conteo)
        )

        # ingresos_por_estado
        _orden_estado = {
            EstadoConciliacion.MATCHEADO: 0,
            EstadoConciliacion.PENDIENTE: 1,
            EstadoConciliacion.SIN_MATCH: 2,
            EstadoConciliacion.PERSONAL: 3,
        }
        ingreso_map = {i.id: i for i in ingresos}
        estado_conteo: dict[str, int] = {}
        estado_monto: dict[str, Dinero] = {}
        for c in conciliaciones:
            ing = ingreso_map.get(c.ingreso_id)
            if ing is None:
                continue
            estado_conteo[c.estado] = estado_conteo.get(c.estado, 0) + 1
            estado_monto[c.estado] = estado_monto.get(c.estado, Dinero(0)) + ing.monto
        ingresos_por_estado = tuple(
            ResumenEstado(estado=e, cantidad=estado_conteo[e], monto_total=estado_monto[e])
            for e in sorted(
                estado_conteo,
                key=lambda x: _orden_estado.get(EstadoConciliacion(x), 99),
            )
        )

        return FlujoCaja(
            mes=mes,
            año=año,
            total_ingresos=total_ingresos,
            total_egresos=total_egresos,
            balance=balance,
            ingresos_conciliados=conciliados,
            ingresos_pendientes=pendientes,
            egresos_por_categoria=tuple(sorted(por_cat.items())),
            ingresos_por_banco=ingresos_por_banco,
            ingresos_por_estado=ingresos_por_estado,
        )
