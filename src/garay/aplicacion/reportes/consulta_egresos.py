"""ConsultaEgresosService — flattened egreso rows for the dashboard."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import EgresoRepository


@dataclass(frozen=True)
class FilaEgresoConsulta:
    fecha: date
    descripcion: str
    monto: Dinero
    categoria: str
    tipo: str
    referencia: str | None
    correo_origen: str | None
    reenviado: bool
    fecha_recibido: datetime.datetime | None


class ConsultaEgresosService:
    def __init__(self, egresos: EgresoRepository) -> None:
        self._egresos = egresos

    def ejecutar(self, desde: date, hasta: date) -> list[FilaEgresoConsulta]:
        return [
            FilaEgresoConsulta(
                fecha=e.fecha,
                descripcion=e.descripcion,
                monto=e.monto,
                categoria=e.categoria,
                tipo=str(e.tipo),
                referencia=e.referencia,
                correo_origen=e.correo_origen,
                reenviado=e.reenviado,
                fecha_recibido=e.fecha_recibido,
            )
            for e in self._egresos.listar_por_periodo(desde, hasta)
        ]
