"""Tests for the METODO_PAGO FSM state — inserted between MONTO_NETO and PARTICIPANTE_ROL."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.comun.tipos import MetodoPago, TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta
from garay.mensajes.catalogo import obtener_mensaje

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ", []),
]
PUNTOS_TEST: list[str] = ["Marie Real"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


def _ctx_con_neto(**kwargs: object) -> ContextoVenta:
    """Build a ContextoVenta with enough fields to reach the MONTO_NETO handler."""
    return ContextoVenta(
        tipo_cliente=TipoCliente.DIGITAL,
        valor=Decimal("100000"),
        neto=None,
        **kwargs,  # type: ignore[arg-type]
    )


def _ctx_post_neto(**kwargs: object) -> ContextoVenta:
    """Build a ContextoVenta that has neto filled — as if MONTO_NETO just completed."""
    return ContextoVenta(
        tipo_cliente=TipoCliente.DIGITAL,
        valor=Decimal("100000"),
        neto=Decimal("50000"),
        **kwargs,  # type: ignore[arg-type]
    )


class TestMontoNetoTransicionAMetodoPago:
    def test_monto_neto_valido_va_a_metodo_pago(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_con_neto()
        resultado = fsm.procesar(EstadoFSM.MONTO_NETO, "50000", ctx)
        assert resultado.nuevo_estado == EstadoFSM.METODO_PAGO

    def test_monto_neto_mensaje_metodo_pago(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_con_neto()
        resultado = fsm.procesar(EstadoFSM.MONTO_NETO, "50000", ctx)
        assert obtener_mensaje("pregunta_metodo_pago") in resultado.mensaje

    def test_monto_neto_opciones_metodo_pago(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_con_neto()
        resultado = fsm.procesar(EstadoFSM.MONTO_NETO, "50000", ctx)
        assert obtener_mensaje("metodo_pago.transferencia") in resultado.opciones
        assert obtener_mensaje("metodo_pago.efectivo") in resultado.opciones
        assert obtener_mensaje("metodo_pago.tarjeta") in resultado.opciones


class TestMontoAbonoIgualValorTransicionAMetodoPago:
    def test_abono_con_neto_calculable_va_a_metodo_pago(self, fsm: FSMTiquetera) -> None:
        """When neto can be computed from the catalog after abono, goes to METODO_PAGO."""
        ctx = ContextoVenta(
            tipo_cliente=TipoCliente.DIGITAL,
            destinos_numeros=[1],
            adultos=1,
            ninos=0,
            valor=Decimal("100000"),
        )
        resultado = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert resultado.nuevo_estado == EstadoFSM.METODO_PAGO


class TestMetodoPagoHandler:
    def test_entrada_invalida_permanece_en_estado(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_post_neto()
        resultado = fsm.procesar(EstadoFSM.METODO_PAGO, "Cheque", ctx)
        assert resultado.nuevo_estado == EstadoFSM.METODO_PAGO

    def test_transferencia_avanza_a_participante_rol(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_post_neto()
        opcion = obtener_mensaje("metodo_pago.transferencia")
        resultado = fsm.procesar(EstadoFSM.METODO_PAGO, opcion, ctx)
        assert resultado.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert resultado.contexto.metodo_pago == MetodoPago.TRANSFERENCIA

    def test_efectivo_avanza_a_participante_rol(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_post_neto()
        opcion = obtener_mensaje("metodo_pago.efectivo")
        resultado = fsm.procesar(EstadoFSM.METODO_PAGO, opcion, ctx)
        assert resultado.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert resultado.contexto.metodo_pago == MetodoPago.EFECTIVO

    def test_tarjeta_avanza_a_participante_rol(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_post_neto()
        opcion = obtener_mensaje("metodo_pago.tarjeta")
        resultado = fsm.procesar(EstadoFSM.METODO_PAGO, opcion, ctx)
        assert resultado.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert resultado.contexto.metodo_pago == MetodoPago.TARJETA

    def test_modo_edicion_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_post_neto(modo_edicion=True)
        opcion = obtener_mensaje("metodo_pago.efectivo")
        resultado = fsm.procesar(EstadoFSM.METODO_PAGO, opcion, ctx)
        assert resultado.nuevo_estado == EstadoFSM.CONFIRMACION
        assert not resultado.contexto.modo_edicion
