"""Entidades del modulo ventas."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import EstadoVenta, TipoCliente
from garay.dominio.ventas.errores import (
    AbonoSuperaValorVenta,
    CantidadInvalida,
    GananciaNegativa,
    MonedaIncompatible,
    ValorVentaInvalido,
)
from garay.dominio.ventas.valor_objetos import Participantes

_CERO = Dinero(0)


@dataclass(eq=False)
class Venta:
    """Aggregate root que representa una transaccion de venta de un servicio."""

    id: uuid.UUID
    valor_venta: Dinero
    neto: Dinero
    servicio_id: uuid.UUID
    cliente_id: uuid.UUID
    tipo_cliente: TipoCliente
    fecha: datetime.date
    participantes: Participantes
    cantidad: int = 1
    abono: Dinero | None = None
    estado: EstadoVenta = field(default=EstadoVenta.PENDIENTE)

    def __post_init__(self) -> None:
        if self.valor_venta.moneda != self.neto.moneda:
            raise MonedaIncompatible(
                f"valor_venta ({self.valor_venta.moneda}) y neto ({self.neto.moneda})"
                " deben ser la misma moneda."
            )
        if self.valor_venta <= _CERO:
            raise ValorVentaInvalido(
                f"El valor de venta debe ser mayor que cero. Recibido: {self.valor_venta}."
            )
        if self.neto > self.valor_venta:
            raise GananciaNegativa(
                f"El neto ({self.neto}) no puede superar el valor de venta ({self.valor_venta})."
            )
        if self.cantidad < 1:
            raise CantidadInvalida("La cantidad de pasajeros debe ser al menos 1.")
        if self.abono is not None and self.abono > self.valor_venta:
            raise AbonoSuperaValorVenta("El abono no puede superar el valor de la venta.")

    @property
    def ganancia(self) -> Dinero:
        return self.valor_venta - self.neto

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Venta) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
