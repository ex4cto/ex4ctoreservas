"""Tests for the pure FSM — Telegram-free, import-only garay.aplicacion.tiquetera.fsm."""
from __future__ import annotations

import pytest

from garay.aplicacion.tiquetera.fsm import (
    ContextoVenta,
    EstadoFSM,
    FSMTiquetera,
)


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera()


@pytest.fixture()
def ctx() -> ContextoVenta:
    return ContextoVenta()


class TestIniciar:
    def test_iniciar_devuelve_estado_tipo_reserva(self, fsm: FSMTiquetera) -> None:
        salida = fsm.iniciar()
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA


class TestTipoReserva:
    def test_tipo_reserva_interno_avanza_a_punto_de_venta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA

    def test_tipo_reserva_externo_avanza_a_punto_de_venta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA


class TestDestino:
    def test_destino_toggle_agrega_y_quita(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        # Toggle adds
        s1 = fsm.procesar(EstadoFSM.DESTINO, "toggle:playa_blanca", ctx)
        assert s1.nuevo_estado == EstadoFSM.DESTINO
        assert "playa_blanca" in s1.contexto.destinos

        # Toggle same item removes it
        s2 = fsm.procesar(EstadoFSM.DESTINO, "toggle:playa_blanca", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.DESTINO
        assert "playa_blanca" not in s2.contexto.destinos

    def test_destino_confirmar_sin_seleccion_devuelve_error(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.DESTINO, "confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.DESTINO

    def test_destino_confirmar_con_seleccion_avanza(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx_con_destino = ContextoVenta(destinos=["playa_blanca"])
        salida = fsm.procesar(EstadoFSM.DESTINO, "confirmar", ctx_con_destino)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE


class TestFechaSalida:
    def test_fecha_invalida_devuelve_error_mismo_estado(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "no-es-fecha", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_fecha_valida_avanza_a_pax_adultos(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS


class TestPax:
    def test_adultos_invalido_devuelve_error(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS


class TestMonto:
    def test_monto_neto_supera_valor_devuelve_error(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        from decimal import Decimal

        ctx_con_valor = ContextoVenta(valor=Decimal("100000"))
        salida = fsm.procesar(EstadoFSM.MONTO_NETO, "200000", ctx_con_valor)
        assert salida.nuevo_estado == EstadoFSM.MONTO_NETO


class TestParticipante:
    def test_rol_ambos_salta_participante_otro(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_rol_vendedor_pide_cerrador(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo vendedor", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO


class TestConfirmacion:
    def test_confirmacion_confirmar_devuelve_terminado_listo(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.TERMINADO
        assert salida.listo is True


class TestCancelar:
    def test_cancelar_desde_cualquier_estado(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.cancelar(ctx)
        assert salida.nuevo_estado == EstadoFSM.CANCELADO


class TestFlujoCompleto:
    def test_flujo_completo_feliz(self, fsm: FSMTiquetera) -> None:
        """Drive FSM through all states with valid inputs — must reach TERMINADO."""
        ctx = ContextoVenta()

        # TIPO_RESERVA
        s = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert s.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA
        ctx = s.contexto

        # PUNTO_DE_VENTA
        s = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s.nuevo_estado == EstadoFSM.DESTINO
        ctx = s.contexto

        # DESTINO — toggle then confirm
        s = fsm.procesar(EstadoFSM.DESTINO, "toggle:playa_blanca", ctx)
        ctx = s.contexto
        s = fsm.procesar(EstadoFSM.DESTINO, "confirmar", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE
        ctx = s.contexto

        # CLIENTE_NOMBRE
        s = fsm.procesar(EstadoFSM.CLIENTE_NOMBRE, "Juan Perez", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_TELEFONO
        ctx = s.contexto

        # CLIENTE_TELEFONO
        s = fsm.procesar(EstadoFSM.CLIENTE_TELEFONO, "3001234567", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_HOTEL
        ctx = s.contexto

        # CLIENTE_HOTEL
        s = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "Hotel Caribe", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_HABITACION
        ctx = s.contexto

        # CLIENTE_HABITACION
        s = fsm.procesar(EstadoFSM.CLIENTE_HABITACION, "301", ctx)
        assert s.nuevo_estado == EstadoFSM.FECHA_SALIDA
        ctx = s.contexto

        # FECHA_SALIDA
        s = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12", ctx)
        assert s.nuevo_estado == EstadoFSM.PAX_ADULTOS
        ctx = s.contexto

        # PAX_ADULTOS
        s = fsm.procesar(EstadoFSM.PAX_ADULTOS, "2", ctx)
        assert s.nuevo_estado == EstadoFSM.PAX_NINOS
        ctx = s.contexto

        # PAX_NINOS
        s = fsm.procesar(EstadoFSM.PAX_NINOS, "0", ctx)
        assert s.nuevo_estado == EstadoFSM.NUMERO_TICKET
        ctx = s.contexto

        # NUMERO_TICKET
        s = fsm.procesar(EstadoFSM.NUMERO_TICKET, "42", ctx)
        assert s.nuevo_estado == EstadoFSM.MONTO_VALOR
        ctx = s.contexto

        # MONTO_VALOR
        s = fsm.procesar(EstadoFSM.MONTO_VALOR, "500.000", ctx)
        assert s.nuevo_estado == EstadoFSM.MONTO_ABONO
        ctx = s.contexto

        # MONTO_ABONO
        s = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert s.nuevo_estado == EstadoFSM.MONTO_NETO
        ctx = s.contexto

        # MONTO_NETO
        s = fsm.procesar(EstadoFSM.MONTO_NETO, "450000", ctx)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_NOMBRE
        ctx = s.contexto

        # PARTICIPANTE_NOMBRE
        s = fsm.procesar(EstadoFSM.PARTICIPANTE_NOMBRE, "Maria Lopez", ctx)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        ctx = s.contexto

        # PARTICIPANTE_ROL — Ambos (skip PARTICIPANTE_OTRO)
        s = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        ctx = s.contexto

        # CONFIRMACION
        s = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx)
        assert s.nuevo_estado == EstadoFSM.TERMINADO
        assert s.listo is True
