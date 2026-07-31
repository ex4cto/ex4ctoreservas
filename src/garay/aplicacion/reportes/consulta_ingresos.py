"""ConsultaIngresosService — flattened ingreso rows for the dashboard."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import IngresoRepository


@dataclass(frozen=True)
class FilaIngresoConsulta:
    fecha: date
    banco: str
    monto: Dinero
    referencia: str
    remitente: str | None
    clasificado: bool
    correo_origen: str | None
    reenviado: bool
    fecha_recibido: datetime.datetime | None


class ConsultaIngresosService:
    def __init__(self, ingresos: IngresoRepository) -> None:
        self._ingresos = ingresos

    def ejecutar(self, desde: date, hasta: date) -> list[FilaIngresoConsulta]:
        return [
            FilaIngresoConsulta(
                fecha=i.fecha,
                banco=i.banco,
                monto=i.monto,
                referencia=i.referencia,
                remitente=i.remitente,
                clasificado=i.clasificado,
                correo_origen=i.correo_origen,
                reenviado=i.reenviado,
                fecha_recibido=i.fecha_recibido,
            )
            for i in self._ingresos.listar_por_periodo(desde, hasta)
        ]
