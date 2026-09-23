"""INTERNO clients now go through hotel + room questions like EXTERNO.

Business rule (corrected): asking for hotel/room is skipped ONLY when the client
says "sin hotel", which implies an EXTERNAL context. INTERNO clients always provide
hotel and room — the previous shortcut (hotel = punto de venta) was incorrect.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ", []),
]
PUNTOS_TEST: list[str] = ["Marie Real"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


class TestIdentificacionRuteoPorTipo:
    def test_interno_va_a_cliente_hotel(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.INTERNO, punto_de_venta_nombre="Marie Real")
        salida = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "1234567890", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HOTEL

    def test_externo_va_a_cliente_hotel(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.EXTERNO, punto_de_venta_nombre="Marie Real")
        salida = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "1234567890", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HOTEL

    def test_interno_con_hotel_va_a_habitacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.INTERNO, punto_de_venta_nombre="Marie Real")
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "Hotel Marie Real", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HABITACION

    def test_sin_hotel_salta_habitacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.INTERNO, punto_de_venta_nombre="Marie Real")
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "sin hotel", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert salida.contexto.sin_hotel is True


class TestOpcionesEditables:
    def test_interno_muestra_hotel_y_habitacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.INTERNO, punto_de_venta_nombre="Marie Real")
        opciones = fsm._opciones_editables(ctx)
        assert "Hotel" in opciones
        assert "Habitación" in opciones

    def test_externo_muestra_hotel_y_habitacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.EXTERNO, punto_de_venta_nombre="Marie Real")
        opciones = fsm._opciones_editables(ctx)
        assert "Hotel" in opciones
        assert "Habitación" in opciones
