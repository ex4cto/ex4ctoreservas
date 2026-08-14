"""Tests for the 3 new FSM states: CLIENTE_EMAIL, CLIENTE_TIPO_ID, CLIENTE_IDENTIFICACION."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ", []),
]
PUNTOS_TEST: list[str] = ["Marie Real"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


@pytest.fixture()
def ctx() -> ContextoVenta:
    return ContextoVenta()


class TestClienteTelefonoTransicion:
    def test_cliente_telefono_transiciona_a_cliente_email(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_TELEFONO, "+573001234567", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_EMAIL

    def test_cliente_telefono_guarda_telefono_en_contexto(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_TELEFONO, "+573001234567", ctx)
        assert salida.contexto.cliente_telefono == "+573001234567"


class TestClienteEmail:
    def test_email_valido_almacenado_y_avanza_a_tipo_id(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_EMAIL, "cliente@example.com", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_TIPO_ID
        assert salida.contexto.cliente_email == "cliente@example.com"

    def test_email_sin_arroba_rechazado(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_EMAIL, "correosindominio", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_EMAIL

    def test_email_invalido_no_guarda_en_contexto(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_EMAIL, "noesunemail", ctx)
        assert salida.contexto.cliente_email is None

    def test_email_modo_edicion_retorna_a_confirmacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx.modo_edicion = True
        ctx.cliente_nombre = "Test"
        ctx.cliente_telefono = "123"
        salida = fsm.procesar(EstadoFSM.CLIENTE_EMAIL, "nuevo@email.com", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.cliente_email == "nuevo@email.com"


class TestClienteTipoId:
    def test_cc_aceptado_y_almacenado(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_TIPO_ID, "CC", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_IDENTIFICACION
        assert salida.contexto.cliente_tipo_identificacion == "CC"

    def test_nit_aceptado_y_almacenado(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_TIPO_ID, "NIT", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_IDENTIFICACION
        assert salida.contexto.cliente_tipo_identificacion == "NIT"

    def test_cc_minusculas_aceptado(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_TIPO_ID, "cc", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_IDENTIFICACION
        assert salida.contexto.cliente_tipo_identificacion == "CC"

    def test_tipo_invalido_rechazado(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_TIPO_ID, "PASAPORTE", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_TIPO_ID

    def test_tipo_id_modo_edicion_retorna_a_confirmacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx.modo_edicion = True
        ctx.cliente_nombre = "Test"
        salida = fsm.procesar(EstadoFSM.CLIENTE_TIPO_ID, "NIT", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.cliente_tipo_identificacion == "NIT"


class TestClienteIdentificacion:
    def test_identificacion_valida_almacenada_y_avanza_a_hotel(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "1234567890", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HOTEL
        assert salida.contexto.cliente_identificacion == "1234567890"

    def test_identificacion_vacia_rechazada(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "   ", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_IDENTIFICACION

    def test_identificacion_modo_edicion_retorna_a_confirmacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx.modo_edicion = True
        ctx.cliente_nombre = "Test"
        salida = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "9876543210", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.cliente_identificacion == "9876543210"

    def test_identificacion_con_espacios_es_trimmed(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "  12345  ", ctx)
        assert salida.contexto.cliente_identificacion == "12345"


class TestValidacionConfirmacion:
    def test_falta_email_listado_en_faltantes(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx.cliente_nombre = "Test"
        ctx.cliente_telefono = "123"
        # email and identificacion are missing
        faltantes = fsm._validar_datos_confirmacion(ctx)
        assert any("correo" in f.lower() or "email" in f.lower() for f in faltantes)

    def test_falta_identificacion_listado_en_faltantes(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx.cliente_nombre = "Test"
        ctx.cliente_telefono = "123"
        ctx.cliente_email = "test@test.com"
        # identificacion is missing
        faltantes = fsm._validar_datos_confirmacion(ctx)
        assert any("identificaci" in f.lower() for f in faltantes)


class TestConstruirResumen:
    def test_resumen_incluye_email(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        import datetime
        from decimal import Decimal

        ctx.tipo_cliente = None
        ctx.cliente_nombre = "Ana"
        ctx.cliente_telefono = "111"
        ctx.cliente_email = "ana@test.com"
        ctx.cliente_identificacion = "ABC123"
        ctx.fecha_salida = datetime.datetime(2026, 8, 1)
        ctx.adultos = 2
        ctx.ninos = 0
        ctx.valor = Decimal("100000")
        ctx.abono = Decimal("0")
        ctx.neto = Decimal("100000")
        resumen = fsm._construir_resumen(ctx)
        assert "ana@test.com" in resumen

    def test_resumen_incluye_identificacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        import datetime
        from decimal import Decimal

        ctx.tipo_cliente = None
        ctx.cliente_nombre = "Ana"
        ctx.cliente_telefono = "111"
        ctx.cliente_email = "ana@test.com"
        ctx.cliente_identificacion = "ABC123"
        ctx.fecha_salida = datetime.datetime(2026, 8, 1)
        ctx.adultos = 2
        ctx.ninos = 0
        ctx.valor = Decimal("100000")
        ctx.abono = Decimal("0")
        ctx.neto = Decimal("100000")
        resumen = fsm._construir_resumen(ctx)
        assert "ABC123" in resumen
