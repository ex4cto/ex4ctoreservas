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
    DigitalConPuntoDeVenta,
    GananciaNegativa,
    MonedaIncompatible,
    ValorVentaInvalido,
    VentaYaAnulada,
)
from garay.dominio.ventas.valor_objetos import Participantes

_CERO = Dinero(0)


@dataclass(eq=False)
class Venta:
    """Aggregate root que representa una transaccion de venta de un servicio."""

    id: uuid.UUID
    valor_venta: Dinero
    neto: Dinero
    servicio_ids: list[uuid.UUID]
    cliente_id: uuid.UUID
    tipo_cliente: TipoCliente
    fecha: datetime.date
    participantes: Participantes
    adultos: int = 1
    ninos: int = 0
    abono: Dinero | None = None
    estado: EstadoVenta = field(default=EstadoVenta.PENDIENTE)
    canal_origen: str | None = None
    fechas_por_servicio: dict[uuid.UUID, datetime.datetime] | None = None
    horarios_por_servicio: dict[uuid.UUID, str] | None = None
    anulada: bool = False
    # Invoice language: "es" (Spanish, default) | "en" (English). Persisted so a
    # regenerated invoice (reenvío) keeps the client's original choice.
    factura_idioma: str = "es"

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
        if self.adultos < 1:
            raise CantidadInvalida("Debe haber al menos 1 adulto.")
        if self.ninos < 0:
            raise CantidadInvalida("El número de niños no puede ser negativo.")
        if self.abono is not None and self.abono > self.valor_venta:
            raise AbonoSuperaValorVenta("El abono no puede superar el valor de la venta.")
        if (
            self.tipo_cliente == TipoCliente.DIGITAL
            and self.participantes.punto_de_venta_id is not None
        ):
            raise DigitalConPuntoDeVenta(
                "Una venta DIGITAL no puede tener un punto de venta asociado."
            )

    def anular(self) -> None:
        """Soft-delete: marks the venta as anulada. Raises VentaYaAnulada if already anulada."""
        if self.anulada:
            raise VentaYaAnulada("La venta ya fue anulada.")
        self.anulada = True

    def cambiar_fecha(self, nueva_fecha: datetime.datetime) -> None:
        """Update the tour date. Raises VentaYaAnulada if the venta is already anulada.

        Updates the scalar ``fecha`` field and, when ``fechas_por_servicio`` has
        exactly one entry, replaces that entry's value with ``nueva_fecha``
        (the servicio_id key is preserved).
        If ``fechas_por_servicio`` is None or has multiple entries only the
        scalar ``fecha`` is updated — the multi-tour case is not in scope for
        Slice B3.
        """
        if self.anulada:
            raise VentaYaAnulada("No se puede editar la fecha de una venta ya anulada.")
        self.fecha = nueva_fecha.date()
        if self.fechas_por_servicio is not None and len(self.fechas_por_servicio) == 1:
            (sid,) = tuple(self.fechas_por_servicio)
            self.fechas_por_servicio[sid] = nueva_fecha

    @property
    def ganancia(self) -> Dinero:
        return self.valor_venta - self.neto

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Venta) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
