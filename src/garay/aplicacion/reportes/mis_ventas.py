"""MisVentasService — a freelancer's own sales view.

Option B: this month's realized tours (fecha ≤ hoy) plus ALL upcoming sold tours
(fecha > hoy, no upper bound). Commission counts only the role(s) the freelancer
actually played on each sale, so a freelancer who was only vendedor does not get
the counterpart's cerrador commission added to their total.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from datetime import date

from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ComisionRegistradaRepository,
    VentaRepository,
)
from garay.dominio.ventas.entidades import Venta


@dataclass(frozen=True)
class LineaMisVentas:
    fecha: date
    valor: Dinero
    varias_fechas: bool
    canal_origen: str | None


@dataclass(frozen=True)
class MisVentas:
    desde: date
    hoy: date
    total_ventas: int
    valor_total: Dinero
    comision_total: Dinero
    realizados: tuple[LineaMisVentas, ...]
    proximos: tuple[LineaMisVentas, ...]


class MisVentasService:
    def __init__(
        self,
        ventas: VentaRepository,
        comisiones: ComisionRegistradaRepository,
    ) -> None:
        self._ventas = ventas
        self._comisiones = comisiones

    def ejecutar(
        self,
        freelancer_id: uuid.UUID,
        freelancer_nombre: str,
        hoy: date,
    ) -> MisVentas:
        desde = date(hoy.year, hoy.month, 1)
        # Option B: no upper bound (date.max) so future tours are included.
        ventas = self._ventas.listar_por_freelancer_y_periodo(
            freelancer_id, freelancer_nombre, desde, datetime.date.max
        )
        comisiones = self._comisiones.listar_por_venta_ids([v.id for v in ventas])
        comision_por_venta = {c.venta_id: c for c in comisiones}

        valor_total = sum((v.valor_venta for v in ventas), start=Dinero(0))
        comision_total = Dinero(0)
        realizados: list[LineaMisVentas] = []
        proximos: list[LineaMisVentas] = []
        for venta in ventas:
            comision_total = comision_total + self._comision_del_freelancer(
                venta, comision_por_venta.get(venta.id), freelancer_id, freelancer_nombre
            )
            linea = LineaMisVentas(
                fecha=venta.fecha,
                valor=venta.valor_venta,
                varias_fechas=(
                    venta.fechas_por_servicio is not None
                    and len(venta.fechas_por_servicio) > 1
                ),
                canal_origen=venta.canal_origen,
            )
            if venta.fecha > hoy:
                proximos.append(linea)
            else:
                realizados.append(linea)

        return MisVentas(
            desde=desde,
            hoy=hoy,
            total_ventas=len(ventas),
            valor_total=valor_total,
            comision_total=comision_total,
            realizados=tuple(sorted(realizados, key=lambda linea: linea.fecha)),
            proximos=tuple(sorted(proximos, key=lambda linea: linea.fecha)),
        )

    @staticmethod
    def _comision_del_freelancer(
        venta: Venta,
        comision: ComisionRegistrada | None,
        freelancer_id: uuid.UUID,
        freelancer_nombre: str,
    ) -> Dinero:
        """Sum only the commission for the role(s) this freelancer played.

        Matches by id when present, else by snapshot name (mirrors the repo's
        listar_por_freelancer_y_periodo selector for legacy rows without ids).
        """
        if comision is None:
            return Dinero(0)
        participantes = venta.participantes
        total = Dinero(0)
        es_vendedor = participantes.vendedor_id == freelancer_id or (
            participantes.vendedor_id is None
            and participantes.vendedor_nombre == freelancer_nombre
        )
        es_cerrador = participantes.cerrador_id == freelancer_id or (
            participantes.cerrador_id is None
            and participantes.cerrador_nombre == freelancer_nombre
        )
        if es_vendedor:
            total = total + comision.desglose.vendedor
        if es_cerrador:
            total = total + comision.desglose.cerrador
        return total
