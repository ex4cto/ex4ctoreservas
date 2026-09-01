"""INTERNO clients skip the hotel/room questions.

Business rule: an INTERNO client is staying at the hotel where the punto de venta
is located, so the hotel is implicit (the punto de venta) and asking for it is
redundant. EXTERNO/DIGITAL still get the hotel questions.
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
    def test_interno_salta_hotel_va_a_fecha_salida(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.INTERNO, punto_de_venta_nombre="Marie Real")
        salida = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "1234567890", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_interno_guarda_punto_como_hotel(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.INTERNO, punto_de_venta_nombre="Marie Real")
        salida = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "1234567890", ctx)
        assert salida.contexto.cliente_hotel == "Marie Real"

    def test_externo_sigue_preguntando_hotel(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.EXTERNO, punto_de_venta_nombre="Marie Real")
        salida = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "1234567890", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HOTEL


class TestValidacionConfirmacionInterno:
    def test_interno_no_exige_hotel_ni_habitacion(self, fsm: FSMTiquetera) -> None:
        """INTERNO no longer requires hotel/habitación (hotel is the punto de venta)."""
        ctx = ContextoVenta(
            tipo_cliente=TipoCliente.INTERNO,
            punto_de_venta_nombre="Marie Real",
            cliente_hotel="Marie Real",
            cliente_habitacion=None,
        )
        faltantes = fsm._validar_datos_confirmacion(ctx)
        assert "Hotel" not in faltantes
        assert "Habitación" not in faltantes


class TestOpcionesEditablesInterno:
    def test_interno_oculta_hotel_y_habitacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.INTERNO, punto_de_venta_nombre="Marie Real")
        opciones = fsm._opciones_editables(ctx)
        assert "Hotel" not in opciones
        assert "Habitación" not in opciones

    def test_externo_conserva_hotel(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(tipo_cliente=TipoCliente.EXTERNO, punto_de_venta_nombre="Marie Real")
        opciones = fsm._opciones_editables(ctx)
        assert "Hotel" in opciones
        assert "Habitación" in opciones
