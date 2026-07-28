"""Commands and result types for the tiquetera application service."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.valor_objetos import Participantes


@dataclass(frozen=True)
class RegistrarVentaComando:
    valor_venta: Dinero
    neto: Dinero
    servicio_ids: list[uuid.UUID]
    cliente_id: uuid.UUID
    tipo_cliente: TipoCliente
    fecha: datetime.date
    participantes: Participantes
    adultos: int
    ninos: int
    foto_referencia: str | None = None
    porcentaje_referido: Decimal = field(default_factory=lambda: Decimal("0"))
    abono: Dinero | None = None
    numero_fisico: str | None = None


@dataclass(frozen=True)
class ResultadoRegistrarVenta:
    venta_id: uuid.UUID
    desglose: DesgloseComision
