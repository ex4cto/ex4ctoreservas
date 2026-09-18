"""Servicio de aplicacion para gestion de obligaciones hoteleras.

Caso de uso: listar hoteles con saldo, calcular saldo actual,
registrar pagos e historico de pagos por hotel.
"""

from __future__ import annotations

import datetime
import uuid

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso, ObligacionHotel
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.dominio.puertos.repositorios import EgresoRepository, ObligacionHotelRepository

_LIMITE_HISTORIAL_DEFAULT = 20


def monto_sugerido(obligacion: ObligacionHotel, today: datetime.date) -> Dinero:
    """Return the suggested payment amount based on which payment day is closest to *today*.

    If the obligacion only has dia_pago_1 (no dia_pago_2), always returns monto_cuota_dia_1.
    When both payment days exist, picks the one whose day-of-month is nearest to today.day.
    Ties go to dia_pago_1.
    """
    if obligacion.dia_pago_2 is None or obligacion.monto_cuota_dia_2 is None:
        return obligacion.monto_cuota_dia_1

    diff_1 = abs(today.day - obligacion.dia_pago_1)
    diff_2 = abs(today.day - obligacion.dia_pago_2)

    if diff_1 <= diff_2:
        return obligacion.monto_cuota_dia_1
    return obligacion.monto_cuota_dia_2


class ServicioHoteles:
    """Application service for hotel payment obligations."""

    def __init__(
        self,
        *,
        obligaciones: ObligacionHotelRepository,
        egresos: EgresoRepository,
    ) -> None:
        self._obligaciones = obligaciones
        self._egresos = egresos

    def listar_con_saldo(self) -> list[tuple[ObligacionHotel, Dinero]]:
        """Return all active hotels paired with their current balance."""
        activas = self._obligaciones.listar_activas()
        return [(o, self.saldo_actual(o.id)) for o in activas]

    def saldo_actual(self, obligacion_id: uuid.UUID) -> Dinero:
        """Compute current balance: deuda_inicial minus sum of all registered payments."""
        obligacion = self._obligaciones.buscar_por_id(obligacion_id)
        if obligacion is None:
            raise ValueError(f"ObligacionHotel not found: {obligacion_id}")
        pagado = self._egresos.sumar_por_obligacion(obligacion_id)
        return obligacion.deuda_inicial - pagado

    def registrar_pago(
        self,
        *,
        obligacion_id: uuid.UUID,
        monto: Dinero,
        fecha: datetime.date,
        concepto: str | None,
        registrado_por_id: int,
    ) -> Egreso:
        """Register a payment against an hotel obligation.

        Creates an Egreso with categoria='cuota_hotel', destinatario=receptor_nombre,
        and obligacion_hotel_id set to the given obligacion.
        """
        obligacion = self._obligaciones.buscar_por_id(obligacion_id)
        if obligacion is None:
            raise ValueError(f"ObligacionHotel not found: {obligacion_id}")

        descripcion = concepto or f"Cuota {obligacion.punto_de_venta_nombre}"

        egreso = Egreso(
            id=uuid.uuid4(),
            descripcion=descripcion,
            monto=monto,
            fecha=fecha,
            categoria="cuota_hotel",
            tipo=TipoEgreso.MANUAL,
            destinatario=obligacion.receptor_nombre,
            obligacion_hotel_id=obligacion_id,
        )
        self._egresos.guardar(egreso)
        return egreso

    def historial(self, obligacion_id: uuid.UUID, limite: int) -> list[Egreso]:
        """Return pagos for this hotel, most recent first."""
        return self._egresos.listar_por_obligacion(obligacion_id, limite)
