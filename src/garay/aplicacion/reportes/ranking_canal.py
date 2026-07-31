"""RankingCanalService — ventas por canal (Hotel / Externas / Crespo) con neto y margen.

Extiende el `por_canal` de ResumenVentas (que solo trae conteo + valor) agregando
costo neto y margen por canal.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import VentaRepository


@dataclass(frozen=True)
class FilaRankingCanal:
    canal: str
    cantidad: int
    valor: Dinero
    neto: Dinero
    margen: Dinero


@dataclass(frozen=True)
class RankingCanal:
    mes: int
    año: int
    filas: tuple[FilaRankingCanal, ...]


class RankingCanalService:
    def __init__(self, ventas: VentaRepository) -> None:
        self._ventas = ventas

    def ejecutar(self, mes: int, año: int) -> RankingCanal:
        desde = date(año, mes, 1)
        hasta = date(año, mes, calendar.monthrange(año, mes)[1])
        ventas = self._ventas.listar_por_periodo(desde, hasta)

        cantidad: dict[str, int] = {}
        valor: dict[str, Dinero] = {}
        neto: dict[str, Dinero] = {}
        for v in ventas:
            canal = v.canal_origen or "Sin canal"
            cantidad[canal] = cantidad.get(canal, 0) + 1
            valor[canal] = valor.get(canal, Dinero(0)) + v.valor_venta
            neto[canal] = neto.get(canal, Dinero(0)) + v.neto

        filas = tuple(
            FilaRankingCanal(
                canal=c,
                cantidad=cantidad[c],
                valor=valor[c],
                neto=neto[c],
                margen=valor[c] - neto[c],
            )
            for c in sorted(cantidad, key=lambda k: valor[k].monto, reverse=True)
        )
        return RankingCanal(mes=mes, año=año, filas=filas)
