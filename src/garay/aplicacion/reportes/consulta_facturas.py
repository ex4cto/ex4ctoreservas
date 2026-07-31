"""ConsultaFacturasService — flattened factura rows for the dashboard."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import FacturaRepository


@dataclass(frozen=True)
class FilaFacturaConsulta:
    numero: str
    fecha_emision: datetime.date
    cliente_nombre: str | None
    cliente_email: str
    monto_total: Dinero
    abono: Dinero | None
    estado_envio: str


class ConsultaFacturasService:
    def __init__(self, facturas: FacturaRepository) -> None:
        self._facturas = facturas

    def ejecutar(self, desde: date, hasta: date) -> list[FilaFacturaConsulta]:
        return [
            FilaFacturaConsulta(
                numero=f.numero,
                fecha_emision=f.fecha_emision,
                cliente_nombre=f.cliente_nombre,
                cliente_email=f.cliente_email,
                monto_total=f.monto_total,
                abono=f.abono,
                estado_envio=str(f.estado_envio),
            )
            for f in self._facturas.listar_por_periodo(desde, hasta)
        ]
