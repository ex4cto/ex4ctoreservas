"""ResumenVentasService — monthly sales summary for dashboard."""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ComisionRegistradaRepository,
    FreelancerRepository,
    VentaRepository,
)

# Type alias for the two-level grouping key used in ResumenVentasService.
# UUID when the participant is id-linked; str (snapshot name) when id is NULL.
BucketKey = uuid.UUID | str


@dataclass(frozen=True)
class ResumenVendedor:
    nombre: str  # render label: display for id-keyed, snapshot for name-keyed
    ventas: int
    valor_total: Dinero
    comision: Dinero
    freelancer_id: uuid.UUID | None = None  # None for name-keyed buckets


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
    por_dia: tuple[tuple[date, int, Dinero], ...] = ()


class ResumenVentasService:
    def __init__(
        self,
        ventas: VentaRepository,
        comisiones: ComisionRegistradaRepository,
        freelancers: FreelancerRepository,
    ) -> None:
        self._ventas = ventas
        self._comisiones = comisiones
        self._freelancers = freelancers

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
                por_dia=(),
            )

        venta_ids = [v.id for v in ventas]
        comisiones = self._comisiones.listar_por_venta_ids(venta_ids)
        comision_por_venta = {c.venta_id: c for c in comisiones}

        total_valor = sum((v.valor_venta for v in ventas), start=Dinero(0))
        ganancia = sum((c.desglose.agencia for c in comisiones), start=Dinero(0))

        # Build display dict once — includes inactive freelancers (for historical rows)
        display_por_id: dict[uuid.UUID, str] = {
            f.id: (f.display or f.nombre) for f in self._freelancers.listar_todos()
        }

        # Two-level bucketing: key = vendedor_id (UUID) when not None,
        # else snapshot string or "Sin asignar".
        comision_por_key: dict[BucketKey, Dinero] = {}
        ventas_por_key: dict[BucketKey, int] = {}
        valor_por_key: dict[BucketKey, Dinero] = {}
        # Map each key to its render label and its freelancer_id (for DTO)
        label_por_key: dict[BucketKey, str] = {}
        id_por_key: dict[BucketKey, uuid.UUID | None] = {}

        for venta in ventas:
            com = comision_por_venta.get(venta.id)
            if com is None:
                continue

            p = venta.participantes

            # Vendedor bucket
            key_v: BucketKey
            if p.vendedor_id is not None:
                key_v = p.vendedor_id
                label_v = display_por_id.get(
                    p.vendedor_id, p.vendedor_nombre or str(p.vendedor_id)
                )
                id_v: uuid.UUID | None = p.vendedor_id
            else:
                key_v = p.vendedor_nombre or "Sin asignar"
                label_v = key_v
                id_v = None

            comision_por_key[key_v] = (
                comision_por_key.get(key_v, Dinero(0)) + com.desglose.vendedor
            )
            ventas_por_key[key_v] = ventas_por_key.get(key_v, 0) + 1
            valor_por_key[key_v] = valor_por_key.get(key_v, Dinero(0)) + venta.valor_venta
            label_por_key[key_v] = label_v
            id_por_key[key_v] = id_v

            # Cerrador bucket
            key_c: BucketKey
            if p.cerrador_id is not None:
                key_c = p.cerrador_id
                label_c = display_por_id.get(
                    p.cerrador_id, p.cerrador_nombre or str(p.cerrador_id)
                )
                id_c: uuid.UUID | None = p.cerrador_id
            else:
                key_c = p.cerrador_nombre or "Sin asignar"
                label_c = key_c
                id_c = None

            comision_por_key[key_c] = (
                comision_por_key.get(key_c, Dinero(0)) + com.desglose.cerrador
            )
            label_por_key[key_c] = label_c
            id_por_key[key_c] = id_c

        all_keys: list[BucketKey] = sorted(
            set(list(comision_por_key.keys()) + list(ventas_por_key.keys())),
            key=lambda k: label_por_key.get(k, str(k)),
        )
        por_vendedor = tuple(
            ResumenVendedor(
                nombre=label_por_key.get(k, str(k)),
                ventas=ventas_por_key.get(k, 0),
                valor_total=valor_por_key.get(k, Dinero(0)),
                comision=comision_por_key.get(k, Dinero(0)),
                freelancer_id=id_por_key.get(k),
            )
            for k in all_keys
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

        conteo_dia: dict[date, int] = {}
        valor_dia: dict[date, Dinero] = {}
        for v in ventas:
            conteo_dia[v.fecha] = conteo_dia.get(v.fecha, 0) + 1
            valor_dia[v.fecha] = valor_dia.get(v.fecha, Dinero(0)) + v.valor_venta
        por_dia: tuple[tuple[date, int, Dinero], ...] = tuple(
            sorted((d, conteo_dia[d], valor_dia[d]) for d in conteo_dia)
        )

        return ResumenVentas(
            mes=mes,
            año=año,
            total_ventas=len(ventas),
            total_valor=total_valor,
            ganancia_agencia=ganancia,
            por_vendedor=por_vendedor,
            por_canal=por_canal,
            por_dia=por_dia,
        )
