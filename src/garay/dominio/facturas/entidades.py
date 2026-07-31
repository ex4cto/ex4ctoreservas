"""Entidades del modulo facturas."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field

from garay.dominio.comun.dinero import Dinero
from garay.dominio.facturas.tipos import EstadoEnvioFactura


@dataclass(eq=False)
class Factura:
    """Factura de servicio persistida, con seguimiento del estado de envio."""

    id: uuid.UUID
    numero: str
    venta_id: uuid.UUID
    cliente_email: str
    monto_total: Dinero
    fecha_emision: datetime.date
    html_contenido: str
    cliente_nombre: str | None = None
    abono: Dinero | None = None
    estado_envio: EstadoEnvioFactura = field(default=EstadoEnvioFactura.PENDIENTE)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Factura) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
