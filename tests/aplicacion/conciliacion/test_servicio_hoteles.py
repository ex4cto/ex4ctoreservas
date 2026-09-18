"""Tests for ServicioHoteles application service.

TDD: RED first — all tests must fail before implementation exists.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Sequence
from unittest.mock import MagicMock

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso, ObligacionHotel
from garay.dominio.conciliacion.tipos import TipoEgreso


# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeObligacionRepo:
    def __init__(self, obligaciones: list[ObligacionHotel] | None = None) -> None:
        self._items: list[ObligacionHotel] = obligaciones or []

    def listar_activas(self) -> list[ObligacionHotel]:
        return [o for o in self._items if o.activa]

    def buscar_por_id(self, id: uuid.UUID) -> ObligacionHotel | None:
        return next((o for o in self._items if o.id == id), None)

    def guardar(self, obligacion: ObligacionHotel) -> None:
        self._items = [o for o in self._items if o.id != obligacion.id]
        self._items.append(obligacion)


class FakeEgresoRepo:
    def __init__(self, egresos: list[Egreso] | None = None) -> None:
        self._items: list[Egreso] = egresos or []

    def guardar(self, egreso: Egreso) -> None:
        self._items.append(egreso)

    def listar_por_obligacion(
        self, obligacion_id: uuid.UUID, limite: int
    ) -> list[Egreso]:
        results = [e for e in self._items if e.obligacion_hotel_id == obligacion_id]
        results.sort(key=lambda e: e.fecha, reverse=True)
        return results[:limite]

    def sumar_por_obligacion(self, obligacion_id: uuid.UUID) -> Dinero:
        total = Dinero(0)
        for e in self._items:
            if e.obligacion_hotel_id == obligacion_id:
                total = total + e.monto
        return total

    # Satisfy abstract interface — unused in these tests
    def buscar_por_id(self, id: uuid.UUID) -> Egreso | None:
        return None

    def existe_referencia(self, referencia: str) -> bool:
        return False

    def listar_recientes(self, minutos: int) -> list[Egreso]:
        return []

    def listar_manuales(self, limite: int) -> list[Egreso]:
        return []

    def listar_por_periodo(
        self, desde: datetime.date, hasta: datetime.date
    ) -> list[Egreso]:
        return []

    def sumar_por_recurrente_en_mes(
        self, gasto_recurrente_id: uuid.UUID, año: int, mes: int
    ) -> Dinero:
        return Dinero(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hotel(
    deuda_inicial: int = 2_400_000,
    cuota_1: int = 400_000,
    cuota_2: int | None = 400_000,
    dia_1: int = 15,
    dia_2: int | None = 30,
) -> ObligacionHotel:
    return ObligacionHotel(
        id=uuid.uuid4(),
        punto_de_venta_nombre="Hostal Dora",
        receptor_nombre="Waldy",
        monto_cuota_dia_1=Dinero(cuota_1),
        monto_cuota_dia_2=Dinero(cuota_2) if cuota_2 is not None else None,
        dia_pago_1=dia_1,
        dia_pago_2=dia_2,
        deuda_inicial=Dinero(deuda_inicial),
        fecha_deuda_inicial=datetime.date(2026, 1, 1),
        activa=True,
    )


def _egreso(obligacion_id: uuid.UUID, monto: int, fecha: datetime.date) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Cuota hotel",
        monto=Dinero(monto),
        fecha=fecha,
        categoria="cuota_hotel",
        obligacion_hotel_id=obligacion_id,
    )


def _make_service(
    obligaciones: list[ObligacionHotel] | None = None,
    egresos: list[Egreso] | None = None,
) -> object:
    from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

    return ServicioHoteles(
        obligaciones=FakeObligacionRepo(obligaciones),
        egresos=FakeEgresoRepo(egresos),
    )


# ---------------------------------------------------------------------------
# Tests — saldo_actual
# ---------------------------------------------------------------------------


class TestSaldoActual:
    def test_sin_pagos_saldo_es_deuda_inicial(self) -> None:
        hotel = _hotel(deuda_inicial=2_400_000)
        svc = _make_service(obligaciones=[hotel])
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        saldo = svc_typed.saldo_actual(hotel.id)
        assert saldo == Dinero(2_400_000)

    def test_con_un_pago_saldo_decrece(self) -> None:
        hotel = _hotel(deuda_inicial=2_400_000)
        egreso = _egreso(hotel.id, 400_000, datetime.date(2026, 9, 15))
        svc = _make_service(obligaciones=[hotel], egresos=[egreso])
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        saldo = svc_typed.saldo_actual(hotel.id)
        assert saldo == Dinero(2_000_000)

    def test_con_multiples_pagos(self) -> None:
        hotel = _hotel(deuda_inicial=2_400_000)
        egresos = [
            _egreso(hotel.id, 400_000, datetime.date(2026, 2, 15)),
            _egreso(hotel.id, 400_000, datetime.date(2026, 3, 15)),
            _egreso(hotel.id, 400_000, datetime.date(2026, 4, 15)),
        ]
        svc = _make_service(obligaciones=[hotel], egresos=egresos)
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        saldo = svc_typed.saldo_actual(hotel.id)
        assert saldo == Dinero(1_200_000)

    def test_hoteles_no_se_mezclan(self) -> None:
        hotel_a = _hotel(deuda_inicial=2_400_000)
        hotel_b = _hotel(deuda_inicial=500_000)
        egreso_b = _egreso(hotel_b.id, 500_000, datetime.date(2026, 9, 15))
        svc = _make_service(obligaciones=[hotel_a, hotel_b], egresos=[egreso_b])
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        # hotel_a no tiene pagos, saldo == deuda_inicial
        assert svc_typed.saldo_actual(hotel_a.id) == Dinero(2_400_000)
        # hotel_b tiene un pago que cubre la deuda
        assert svc_typed.saldo_actual(hotel_b.id) == Dinero(0)


# ---------------------------------------------------------------------------
# Tests — registrar_pago
# ---------------------------------------------------------------------------


class TestRegistrarPago:
    def test_registrar_pago_crea_egreso(self) -> None:
        hotel = _hotel(deuda_inicial=2_400_000)
        svc = _make_service(obligaciones=[hotel], egresos=[])
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        egreso = svc_typed.registrar_pago(
            obligacion_id=hotel.id,
            monto=Dinero(400_000),
            fecha=datetime.date(2026, 9, 15),
            concepto="Cuota septiembre",
            registrado_por_id=12345,
        )
        assert egreso.monto == Dinero(400_000)
        assert egreso.fecha == datetime.date(2026, 9, 15)
        assert egreso.obligacion_hotel_id == hotel.id
        assert egreso.categoria == "cuota_hotel"
        assert egreso.destinatario == hotel.receptor_nombre

    def test_registrar_pago_reduce_saldo(self) -> None:
        hotel = _hotel(deuda_inicial=2_400_000)
        svc = _make_service(obligaciones=[hotel], egresos=[])
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        svc_typed.registrar_pago(
            obligacion_id=hotel.id,
            monto=Dinero(400_000),
            fecha=datetime.date(2026, 9, 15),
            concepto="Cuota septiembre",
            registrado_por_id=12345,
        )
        assert svc_typed.saldo_actual(hotel.id) == Dinero(2_000_000)

    def test_registrar_pago_sin_concepto_usa_descripcion_default(self) -> None:
        hotel = _hotel()
        svc = _make_service(obligaciones=[hotel])
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        egreso = svc_typed.registrar_pago(
            obligacion_id=hotel.id,
            monto=Dinero(400_000),
            fecha=datetime.date(2026, 9, 15),
            concepto=None,
            registrado_por_id=12345,
        )
        assert egreso.descripcion  # not empty
        assert len(egreso.descripcion) > 0


# ---------------------------------------------------------------------------
# Tests — monto_sugerido
# ---------------------------------------------------------------------------


class TestMontoSugerido:
    def test_antes_del_dia_1_usa_cuota_1(self) -> None:
        from garay.aplicacion.conciliacion.servicio_hoteles import monto_sugerido

        hotel = _hotel(cuota_1=400_000, cuota_2=400_000, dia_1=15, dia_2=30)
        # day 10 is closer to dia_pago_1=15 than dia_pago_2=30
        resultado = monto_sugerido(hotel, datetime.date(2026, 9, 10))
        assert resultado == Dinero(400_000)

    def test_dia_exacto_1_usa_cuota_1(self) -> None:
        from garay.aplicacion.conciliacion.servicio_hoteles import monto_sugerido

        hotel = _hotel(cuota_1=1_000_000, cuota_2=1_000_000, dia_1=15, dia_2=30)
        resultado = monto_sugerido(hotel, datetime.date(2026, 9, 15))
        assert resultado == Dinero(1_000_000)

    def test_despues_de_mitad_usa_cuota_2(self) -> None:
        from garay.aplicacion.conciliacion.servicio_hoteles import monto_sugerido

        hotel = _hotel(cuota_1=750_000, cuota_2=950_000, dia_1=15, dia_2=30)
        # day 25 is closer to dia_pago_2=30 than dia_pago_1=15
        resultado = monto_sugerido(hotel, datetime.date(2026, 9, 25))
        assert resultado == Dinero(950_000)

    def test_sin_cuota_2_siempre_usa_cuota_1(self) -> None:
        from garay.aplicacion.conciliacion.servicio_hoteles import monto_sugerido

        hotel = _hotel(cuota_1=500_000, cuota_2=None, dia_1=15, dia_2=None)
        resultado = monto_sugerido(hotel, datetime.date(2026, 9, 28))
        assert resultado == Dinero(500_000)

    def test_cuotas_diferentes_selecciona_correcta(self) -> None:
        from garay.aplicacion.conciliacion.servicio_hoteles import monto_sugerido

        hotel = _hotel(cuota_1=750_000, cuota_2=950_000, dia_1=15, dia_2=30)
        # day 3 is closer to dia_pago_1=15 (diff=12) than dia_pago_2=30 (diff=27)
        resultado_inicio = monto_sugerido(hotel, datetime.date(2026, 9, 3))
        assert resultado_inicio == Dinero(750_000)


# ---------------------------------------------------------------------------
# Tests — listar_con_saldo
# ---------------------------------------------------------------------------


class TestListarConSaldo:
    def test_lista_hoteles_activos_con_saldo(self) -> None:
        hotel_a = _hotel(deuda_inicial=2_400_000)
        hotel_b = _hotel(deuda_inicial=500_000)
        egreso_a = _egreso(hotel_a.id, 400_000, datetime.date(2026, 9, 15))
        svc = _make_service(obligaciones=[hotel_a, hotel_b], egresos=[egreso_a])
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        resultado = svc_typed.listar_con_saldo()
        assert len(resultado) == 2
        saldos = {o.id: s for o, s in resultado}
        assert saldos[hotel_a.id] == Dinero(2_000_000)
        assert saldos[hotel_b.id] == Dinero(500_000)

    def test_inactivos_no_aparecen(self) -> None:
        hotel_activo = _hotel(deuda_inicial=500_000)
        hotel_inactivo = ObligacionHotel(
            id=uuid.uuid4(),
            punto_de_venta_nombre="Hotel Cerrado",
            receptor_nombre="Nadie",
            monto_cuota_dia_1=Dinero(0),
            monto_cuota_dia_2=None,
            dia_pago_1=1,
            dia_pago_2=None,
            deuda_inicial=Dinero(0),
            fecha_deuda_inicial=datetime.date(2026, 1, 1),
            activa=False,
        )
        svc = _make_service(obligaciones=[hotel_activo, hotel_inactivo])
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        resultado = svc_typed.listar_con_saldo()
        ids = [o.id for o, _ in resultado]
        assert hotel_activo.id in ids
        assert hotel_inactivo.id not in ids


# ---------------------------------------------------------------------------
# Tests — historial
# ---------------------------------------------------------------------------


class TestHistorial:
    def test_historial_devuelve_pagos_en_orden_inverso(self) -> None:
        hotel = _hotel()
        e1 = _egreso(hotel.id, 400_000, datetime.date(2026, 7, 15))
        e2 = _egreso(hotel.id, 400_000, datetime.date(2026, 8, 15))
        e3 = _egreso(hotel.id, 400_000, datetime.date(2026, 9, 15))
        svc = _make_service(obligaciones=[hotel], egresos=[e1, e2, e3])
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        hist = svc_typed.historial(hotel.id, limite=10)
        assert hist[0].fecha == datetime.date(2026, 9, 15)
        assert hist[2].fecha == datetime.date(2026, 7, 15)

    def test_historial_respeta_limite(self) -> None:
        hotel = _hotel()
        egresos = [
            _egreso(hotel.id, 400_000, datetime.date(2026, i, 15))
            for i in range(1, 6)
        ]
        svc = _make_service(obligaciones=[hotel], egresos=egresos)
        from garay.aplicacion.conciliacion.servicio_hoteles import ServicioHoteles

        svc_typed: ServicioHoteles = svc  # type: ignore[assignment]
        hist = svc_typed.historial(hotel.id, limite=3)
        assert len(hist) == 3
