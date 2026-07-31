"""RankingTourService — ventas agrupadas por familia de tour (Servicio.categoria).

La familia sale de la categoria del catalogo (las 16 oficiales del price-list).
Ordena por cantidad vendida desc (desempata por margen), para ver que familia se
vende mas y cual deja mas utilidad.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ComisionRegistradaRepository,
    ServicioRepository,
    VentaRepository,
)

_SIN_CATEGORIA = "Sin categoria"


@dataclass(frozen=True)
class FilaRankingTour:
    familia: str
    vendidos: int
    valor: Dinero
    neto: Dinero
    margen: Dinero
    agencia: Dinero


@dataclass(frozen=True)
class RankingTour:
    mes: int
    año: int
    filas: tuple[FilaRankingTour, ...]


class RankingTourService:
    def __init__(
        self,
        ventas: VentaRepository,
        comisiones: ComisionRegistradaRepository,
        servicios: ServicioRepository,
    ) -> None:
        self._ventas = ventas
        self._comisiones = comisiones
        self._servicios = servicios

    def ejecutar(self, mes: int, año: int) -> RankingTour:
        desde = date(año, mes, 1)
        hasta = date(año, mes, calendar.monthrange(año, mes)[1])
        ventas = self._ventas.listar_por_periodo(desde, hasta)

        familia_por_servicio = {
            s.id: (s.categoria or _SIN_CATEGORIA) for s in self._servicios.listar()
        }
        comisiones = self._comisiones.listar_por_venta_ids([v.id for v in ventas])
        agencia_por_venta = {c.venta_id: c.desglose.agencia for c in comisiones}

        vendidos: dict[str, int] = {}
        valor: dict[str, Dinero] = {}
        neto: dict[str, Dinero] = {}
        agencia: dict[str, Dinero] = {}
        for v in ventas:
            fam = (
                familia_por_servicio.get(v.servicio_ids[0], _SIN_CATEGORIA)
                if v.servicio_ids
                else _SIN_CATEGORIA
            )
            vendidos[fam] = vendidos.get(fam, 0) + 1
            valor[fam] = valor.get(fam, Dinero(0)) + v.valor_venta
            neto[fam] = neto.get(fam, Dinero(0)) + v.neto
            agencia[fam] = agencia.get(fam, Dinero(0)) + agencia_por_venta.get(v.id, Dinero(0))

        filas = tuple(
            FilaRankingTour(
                familia=fam,
                vendidos=vendidos[fam],
                valor=valor[fam],
                neto=neto[fam],
                margen=valor[fam] - neto[fam],
                agencia=agencia[fam],
            )
            for fam in sorted(
                vendidos,
                key=lambda f: (vendidos[f], (valor[f] - neto[f]).monto),
                reverse=True,
            )
        )
        return RankingTour(mes=mes, año=año, filas=filas)
