"""Tests for the pure FSM — Telegram-free, import-only garay.aplicacion.tiquetera.fsm."""
from __future__ import annotations

from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import (
    ContextoVenta,
    EstadoFSM,
    FSMTiquetera,
)

SERVICIOS_TEST: list[tuple[int, str]] = [
    (1, "Tour Playa Blanca"),
    (2, "Tour Isla"),
    (3, "City Tour"),
]
PUNTOS_TEST: list[str] = ["Marie Real", "Mama Waldi", "Sin punto"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


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
        s1 = fsm.procesar(EstadoFSM.DESTINO, "toggle:1", ctx)
        assert s1.nuevo_estado == EstadoFSM.DESTINO
        assert 1 in s1.contexto.destinos_numeros

        # Toggle same item removes it
        s2 = fsm.procesar(EstadoFSM.DESTINO, "toggle:1", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.DESTINO
        assert 1 not in s2.contexto.destinos_numeros

    def test_destino_confirmar_sin_seleccion_devuelve_error(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.DESTINO, "confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.DESTINO

    def test_destino_confirmar_con_seleccion_avanza(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx_con_destino = ContextoVenta(destinos_numeros=[1])
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
        ctx_con_valor = ContextoVenta(valor=Decimal("100000"))
        salida = fsm.procesar(EstadoFSM.MONTO_NETO, "200000", ctx_con_valor)
        assert salida.nuevo_estado == EstadoFSM.MONTO_NETO


class TestNumeroTicket:
    def test_numero_valido_avanza_a_monto_valor(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        s = fsm.procesar(EstadoFSM.NUMERO_TICKET, "42", ctx)
        assert s.nuevo_estado == EstadoFSM.MONTO_VALOR
        assert s.contexto.numero_fisico == 42

    def test_cero_guarda_none(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        s = fsm.procesar(EstadoFSM.NUMERO_TICKET, "0", ctx)
        assert s.nuevo_estado == EstadoFSM.MONTO_VALOR
        assert s.contexto.numero_fisico is None

    def test_texto_invalido_devuelve_error(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        s = fsm.procesar(EstadoFSM.NUMERO_TICKET, "abc", ctx)
        assert s.nuevo_estado == EstadoFSM.NUMERO_TICKET


class TestParticipante:
    def test_rol_ambos_salta_a_confirmacion(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        s = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s.contexto.rol_registrante == "ambos"

    def test_rol_solo_vendedor_pide_cerrador(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        s = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo vendedor", ctx)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO

    def test_rol_solo_cerrador_pide_vendedor(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        s = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo cerrador", ctx)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO

    def test_participante_otro_como_vendedor_completa(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx_prep = ContextoVenta(rol_registrante="vendedor")
        s = fsm.procesar(EstadoFSM.PARTICIPANTE_OTRO, "Pedro", ctx_prep)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s.contexto.cerrador_nombre == "Pedro"

    def test_participante_otro_como_cerrador_completa(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx_prep = ContextoVenta(rol_registrante="cerrador")
        s = fsm.procesar(EstadoFSM.PARTICIPANTE_OTRO, "Juan", ctx_prep)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s.contexto.vendedor_nombre == "Juan"


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


class TestDestinoDesdeIA:
    """Tests for IA-seeded destinos_nombres pre-population and UI hints."""

    def test_contexto_venta_tiene_campo_destinos_nombres(self) -> None:
        """5.1 — ContextoVenta must have destinos_nombres field defaulting to []."""
        ctx = ContextoVenta()
        assert ctx.destinos_nombres == []

    def test_destinos_nombres_se_puede_inicializar(self) -> None:
        """5.1 — destinos_nombres can be set on construction."""
        ctx = ContextoVenta(destinos_nombres=["Tour Playa Blanca"])
        assert ctx.destinos_nombres == ["Tour Playa Blanca"]

    def test_prepoblacion_exacta(self, fsm: FSMTiquetera) -> None:
        """5.3B — nombre exacto matchea y pre-popula destinos_numeros."""
        ctx = ContextoVenta(destinos_nombres=["Tour Playa Blanca"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert 1 in salida.contexto.destinos_numeros

    def test_prepoblacion_case_insensitive(self, fsm: FSMTiquetera) -> None:
        """5.3B — match es case-insensitive."""
        ctx = ContextoVenta(destinos_nombres=["tour playa blanca"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert 1 in salida.contexto.destinos_numeros

    def test_encabezado_ia_detectado_aparece_con_match(self, fsm: FSMTiquetera) -> None:
        """5.3A — mensaje incluye encabezado cuando al menos un nombre matchea."""
        ctx = ContextoVenta(destinos_nombres=["Tour Playa Blanca"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert "La IA detectó" in salida.mensaje

    def test_sin_match_no_hay_encabezado_ia(self, fsm: FSMTiquetera) -> None:
        """5.3A — mensaje NO incluye encabezado cuando ningún nombre matchea."""
        ctx = ContextoVenta(destinos_nombres=["Destino Inventado"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert "La IA detectó" not in salida.mensaje

    def test_nombres_sin_match_no_agregan_numeros(self, fsm: FSMTiquetera) -> None:
        """5.3B — nombres sin match no agregan números al contexto."""
        ctx = ContextoVenta(destinos_nombres=["Destino Inventado"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.contexto.destinos_numeros == []


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
        s = fsm.procesar(EstadoFSM.DESTINO, "toggle:1", ctx)
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


class TestProcesarFoto:
    """Tests for procesar_foto() — photo AI pre-filled auto-advance logic."""

    def test_procesar_foto_sin_ctx_se_comporta_igual_que_procesar(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """Empty ctx: procesar_foto behaves identical to procesar."""
        salida_proc = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        salida_foto = fsm.procesar_foto(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert salida_proc.nuevo_estado == salida_foto.nuevo_estado

    def test_procesar_foto_auto_avanza_cliente_nombre_prefilled(
        self, fsm: FSMTiquetera
    ) -> None:
        """ctx with cliente_nombre set: after DESTINO→confirmar reaches CLIENTE_TELEFONO."""
        ctx = ContextoVenta(destinos_numeros=[1], cliente_nombre="Juan")
        salida = fsm.procesar_foto(EstadoFSM.DESTINO, "confirmar", ctx)
        # DESTINO→confirmar → CLIENTE_NOMBRE → auto-advance to CLIENTE_TELEFONO
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_TELEFONO
        assert salida.contexto.cliente_nombre == "Juan"

    def test_procesar_foto_no_avanza_sin_valor(
        self, fsm: FSMTiquetera
    ) -> None:
        """ctx without cliente_nombre: stays at CLIENTE_NOMBRE."""
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm.procesar_foto(EstadoFSM.DESTINO, "confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE

    def test_procesar_foto_pax_adultos_cero_no_avanza(
        self, fsm: FSMTiquetera
    ) -> None:
        """adultos=0 should NOT auto-advance PAX_ADULTOS (business rule: min 1)."""
        import datetime
        ctx = ContextoVenta(
            destinos_numeros=[1],
            cliente_nombre="Juan",
            cliente_telefono="300",
            cliente_hotel="Hotel",
            cliente_habitacion="101",
            fecha_salida=datetime.datetime(2026, 12, 25, 10, 0),
            adultos=0,
        )
        salida = fsm.procesar_foto(EstadoFSM.CLIENTE_HABITACION, "101", ctx)
        # Should advance through FECHA_SALIDA (pre-filled) but stop at PAX_ADULTOS (adultos=0)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS

    def test_procesar_foto_pax_adultos_uno_avanza(
        self, fsm: FSMTiquetera
    ) -> None:
        """adultos=1 should auto-advance PAX_ADULTOS."""
        import datetime
        ctx = ContextoVenta(
            destinos_numeros=[1],
            cliente_nombre="Juan",
            cliente_telefono="300",
            cliente_hotel="Hotel",
            cliente_habitacion="101",
            fecha_salida=datetime.datetime(2026, 12, 25, 10, 0),
            adultos=1,
            ninos=None,
        )
        salida = fsm.procesar_foto(EstadoFSM.CLIENTE_HABITACION, "101", ctx)
        # CLIENTE_HABITACION→FECHA_SALIDA (pre-filled)→PAX_ADULTOS (pre-filled, 1)
        # →PAX_NINOS (ninos=None, stops)
        assert salida.nuevo_estado == EstadoFSM.PAX_NINOS
