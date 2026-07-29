"""ResumenVentasService — monthly sales summary for dashboard."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import ComisionRegistradaRepository, VentaRepository


@dataclass(frozen=True)
class ResumenVendedor:
    nombre: str
    ventas: int
    valor_total: Dinero
    comision: Dinero


@dataclass(frozen=True)
class ResumenCanal:
    canal: str
    cantidad: int
    valor_total: Dinero


@dataclass(frozen=True)
class ResumenVentas:
    mes: int
    año: int
    total_ventas: int
    total_valor: Dinero
    ganancia_agencia: Dinero
    por_vendedor: tuple[ResumenVendedor, ...]
    por_canal: tuple[ResumenCanal, ...] = ()


class ResumenVentasService:
    def __init__(
        self,
        ventas: VentaRepository,
        comisiones: ComisionRegistradaRepository,
    ) -> None:
        self._ventas = ventas
        self._comisiones = comisiones

    def ejecutar(self, mes: int, año: int) -> ResumenVentas:
        desde = date(año, mes, 1)
        hasta = date(año, mes, calendar.monthrange(año, mes)[1])
        ventas = self._ventas.listar_por_periodo(desde, hasta)

        if not ventas:
            return ResumenVentas(
                mes=mes,
                año=año,
                total_ventas=0,
                total_valor=Dinero(0),
                ganancia_agencia=Dinero(0),
                por_vendedor=(),
                por_canal=(),
            )

        venta_ids = [v.id for v in ventas]
        comisiones = self._comisiones.listar_por_venta_ids(venta_ids)
        comision_por_venta = {c.venta_id: c for c in comisiones}

        total_valor = sum((v.valor_venta for v in ventas), start=Dinero(0))
        ganancia = sum((c.desglose.agencia for c in comisiones), start=Dinero(0))

        # Accumulate commissions per participant name (vendedor + cerrador tracked separately)
        comision_por_nombre: dict[str, Dinero] = {}
        ventas_por_nombre: dict[str, int] = {}
        valor_por_nombre: dict[str, Dinero] = {}

        for venta in ventas:
            com = comision_por_venta.get(venta.id)
            if com is None:
                continue
            nombre_v = venta.participantes.vendedor_nombre or "Sin asignar"
            nombre_c = venta.participantes.cerrador_nombre or "Sin asignar"

            comision_por_nombre[nombre_v] = (
                comision_por_nombre.get(nombre_v, Dinero(0)) + com.desglose.vendedor
            )
            comision_por_nombre[nombre_c] = (
                comision_por_nombre.get(nombre_c, Dinero(0)) + com.desglose.cerrador
            )
            ventas_por_nombre[nombre_v] = ventas_por_nombre.get(nombre_v, 0) + 1
            valor_por_nombre[nombre_v] = (
                valor_por_nombre.get(nombre_v, Dinero(0)) + venta.valor_venta
            )

        nombres = sorted(set(list(comision_por_nombre.keys()) + list(ventas_por_nombre.keys())))
        por_vendedor = tuple(
            ResumenVendedor(
                nombre=n,
                ventas=ventas_por_nombre.get(n, 0),
                valor_total=valor_por_nombre.get(n, Dinero(0)),
                comision=comision_por_nombre.get(n, Dinero(0)),
            )
            for n in nombres
        )

        conteo_canal: dict[str, int] = {}
        valor_canal: dict[str, Dinero] = {}
        for venta in ventas:
            if venta.canal_origen is not None:
                canal = venta.canal_origen
                conteo_canal[canal] = conteo_canal.get(canal, 0) + 1
                valor_canal[canal] = valor_canal.get(canal, Dinero(0)) + venta.valor_venta

        por_canal = tuple(
            ResumenCanal(canal=c, cantidad=conteo_canal[c], valor_total=valor_canal[c])
            for c in sorted(conteo_canal)
        )

        return ResumenVentas(
            mes=mes,
            año=año,
            total_ventas=len(ventas),
            total_valor=total_valor,
            ganancia_agencia=ganancia,
            por_vendedor=por_vendedor,
            por_canal=por_canal,
        )
