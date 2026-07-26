"""Tests for the pure FSM — Telegram-free, import-only garay.aplicacion.tiquetera.fsm."""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import (
    ContextoVenta,
    EstadoFSM,
    FSMTiquetera,
)

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000")),
    (2, "Tour Isla", Decimal("150000"), None),
    (3, "City Tour", None, None),
]
PUNTOS_TEST: list[str] = ["Marie Real", "Mama Waldi", "Sin punto"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


@pytest.fixture()
def ctx() -> ContextoVenta:
    return ContextoVenta()


class TestIniciar:
    def test_iniciar_devuelve_estado_metodo_input(self, fsm: FSMTiquetera) -> None:
        salida = fsm.iniciar()
        assert salida.nuevo_estado == EstadoFSM.METODO_INPUT
        assert "Manual" in salida.opciones
        assert "Foto" in salida.opciones


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
    def test_destino_numero_agrega(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        s1 = fsm.procesar(EstadoFSM.DESTINO, "1", ctx)
        assert s1.nuevo_estado == EstadoFSM.DESTINO
        assert 1 in s1.contexto.destinos_numeros

    def test_destino_multiples_numeros(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        s = fsm.procesar(EstadoFSM.DESTINO, "1, 2", ctx)
        assert s.nuevo_estado == EstadoFSM.DESTINO
        assert 1 in s.contexto.destinos_numeros
        assert 2 in s.contexto.destinos_numeros

    def test_destino_numero_invalido_devuelve_error(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        s = fsm.procesar(EstadoFSM.DESTINO, "9999", ctx)
        assert s.nuevo_estado == EstadoFSM.DESTINO
        assert 9999 not in s.contexto.destinos_numeros

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

    def test_pax_ninos_avanza_a_monto_valor(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """After WU-3: PAX_NINOS transitions directly to MONTO_VALOR (no NUMERO_TICKET)."""
        salida = fsm.procesar(EstadoFSM.PAX_NINOS, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.MONTO_VALOR


class TestMonto:
    def test_monto_neto_estado_acepta_valor_valido(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """MONTO_NETO fallback state still works when neto_adulto is None."""
        ctx_con_valor = ContextoVenta(valor=Decimal("100000"))
        salida = fsm.procesar(EstadoFSM.MONTO_NETO, "50000", ctx_con_valor)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_monto_neto_supera_valor_devuelve_error(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx_con_valor = ContextoVenta(valor=Decimal("100000"))
        salida = fsm.procesar(EstadoFSM.MONTO_NETO, "200000", ctx_con_valor)
        assert salida.nuevo_estado == EstadoFSM.MONTO_NETO


class TestHotelSkip:
    """WU-5: hotel skip — 'no'/'sin hotel'/etc. jumps to FECHA_SALIDA."""

    def test_hotel_no_salta_fecha_salida(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "no", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert salida.contexto.sin_hotel is True

    def test_hotel_variantes_sin_hotel(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        for variante in ("No", "no hotel", "sin hotel", "no hay"):
            salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, variante, ctx)
            assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA, f"Failed for: {variante!r}"

    def test_hotel_con_nombre_avanza_a_habitacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "Grand Hyatt", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HABITACION
        assert salida.contexto.sin_hotel is False

    def test_habitacion_entry_normal(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HABITACION, "301", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA


class TestFechaFormatos:
    """WU-5: two-digit year format support."""

    def test_fecha_dd_mm_yy_valida(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/26", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS
        assert salida.contexto.fecha_salida is not None
        assert salida.contexto.fecha_salida.year == 2026
        assert salida.contexto.fecha_salida.month == 12
        assert salida.contexto.fecha_salida.day == 25

    def test_fecha_dd_mm_yyyy_sigue_funcionando(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS
        assert salida.contexto.fecha_salida is not None
        assert salida.contexto.fecha_salida.year == 2026


class TestDestinoDeseleccion:
    """WU-5: deselection via '-N' prefix."""

    def test_deseleccion_quita_numero(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm.procesar(EstadoFSM.DESTINO, "-1", ctx)
        assert salida.nuevo_estado == EstadoFSM.DESTINO
        assert 1 not in salida.contexto.destinos_numeros

    def test_deseleccion_numero_no_en_lista(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm.procesar(EstadoFSM.DESTINO, "-99", ctx)
        assert 1 in salida.contexto.destinos_numeros  # list unchanged

    def test_deseleccion_varios(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1, 2])
        salida = fsm.procesar(EstadoFSM.DESTINO, "-1, -2", ctx)
        assert 1 not in salida.contexto.destinos_numeros
        assert 2 not in salida.contexto.destinos_numeros


class TestOpcionesDestino:
    """WU-5: context-aware destination options."""

    def test_sin_seleccion_no_tiene_confirmar(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.DESTINO, "9999", ctx)
        assert "confirmar" not in salida.opciones

    def test_con_seleccion_tiene_confirmar(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm.procesar(EstadoFSM.DESTINO, "2", ctx)
        assert "confirmar" in salida.opciones


class TestNetoAutoCalculo:
    """WU-5: automatic neto calculation from service catalog."""

    def test_neto_auto_calcula_un_servicio(self, fsm: FSMTiquetera) -> None:
        # Service 1: neto_adulto=100000, neto_nino=50000; 2 adultos, 1 nino
        ctx = ContextoVenta(destinos_numeros=[1], adultos=2, ninos=1)
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.neto == Decimal("250000")  # 100000*2 + 50000*1

    def test_neto_auto_calcula_multi_servicio(self, fsm: FSMTiquetera) -> None:
        # Services 1+2: (100000+150000)*2 adultos = 500000
        ctx = ContextoVenta(destinos_numeros=[1, 2], adultos=2, ninos=0)
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.neto == Decimal("500000")

    def test_neto_sin_precio_pide_manual(self, fsm: FSMTiquetera) -> None:
        # Service 3 has neto_adulto=None → fallback to MONTO_NETO
        ctx = ContextoVenta(destinos_numeros=[3], adultos=2, ninos=0)
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.MONTO_NETO

    def test_neto_nino_none_usa_adulto_como_proxy(self, fsm: FSMTiquetera) -> None:
        # Service 2: neto_adulto=150000, neto_nino=None; 1 adult + 1 child
        # Business rule: neto_nino=None → use neto_adulto as proxy
        ctx = ContextoVenta(destinos_numeros=[2], adultos=1, ninos=1)
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.neto == Decimal("300000")  # 150000*1 + 150000*1 (proxy)

    def test_neto_abono_supera_calculado_error(self, fsm: FSMTiquetera) -> None:
        # Abono > neto calculado → MONTO_ABONO with error
        ctx = ContextoVenta(destinos_numeros=[1], adultos=1, ninos=0)
        # neto calculado = 100000; abono = 200000
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "200000", ctx)
        assert salida.nuevo_estado == EstadoFSM.MONTO_ABONO


class TestResumen:
    """WU-5: summary shows tour names, not numbers; no Ticket N°; sin hotel sentinel."""

    def test_resumen_muestra_nombre_tour_no_numero(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(
            destinos_numeros=[1],
            rol_registrante="ambos",
        )
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert "Tour Playa Blanca" in salida.mensaje
        assert "Destinos: 1" not in salida.mensaje

    def test_resumen_sin_ticket_fisico(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(rol_registrante="ambos")
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert "Ticket N°" not in salida.mensaje


class TestConfirmacionEditar:
    """WU-5: Editar option from CONFIRMACION returns to TIPO_RESERVA."""

    def test_confirmacion_editar_vuelve_a_tipo_reserva(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✏️ Editar", ctx)
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA
        assert "INTERNO" in salida.opciones

    def test_confirmacion_confirmar_termina(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.TERMINADO
        assert salida.listo is True

    def test_confirmacion_cancelar_cancela(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "❌ Cancelar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CANCELADO


class TestMetodoInput:
    """WU-6: METODO_INPUT is the first state returned by iniciar()."""

    def test_metodo_input_manual_avanza_a_tipo_reserva(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.METODO_INPUT, "Manual", ctx)
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA

    def test_metodo_input_foto_avanza_a_tipo_reserva(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.METODO_INPUT, "Foto", ctx)
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA

    def test_metodo_input_invalido_repite(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.METODO_INPUT, "Audio", ctx)
        assert salida.nuevo_estado == EstadoFSM.METODO_INPUT

    def test_metodo_input_muestra_opciones_manual_foto(self, fsm: FSMTiquetera) -> None:
        salida = fsm.iniciar()
        assert "Manual" in salida.opciones
        assert "Foto" in salida.opciones


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
        """5.3A — cuando nombre matchea, el número se pre-selecciona y aparece en Seleccionados."""
        ctx = ContextoVenta(destinos_nombres=["Tour Playa Blanca"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert 1 in salida.contexto.destinos_numeros
        assert "Seleccionados" in salida.mensaje

    def test_sin_match_muestra_hint_para_ingresar_numero(self, fsm: FSMTiquetera) -> None:
        """5.3A — cuando nombre no matchea, muestra hint para ingresar el número manualmente."""
        ctx = ContextoVenta(destinos_nombres=["Destino Inventado"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.contexto.destinos_numeros == []
        assert "La IA detectó" in salida.mensaje

    def test_nombres_sin_match_no_agregan_numeros(self, fsm: FSMTiquetera) -> None:
        """5.3B — nombres sin match no agregan números al contexto."""
        ctx = ContextoVenta(destinos_nombres=["Destino Inventado"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.contexto.destinos_numeros == []


class TestFlujoCompleto:
    def test_flujo_completo_feliz(self, fsm: FSMTiquetera) -> None:
        """Drive FSM through all states with valid inputs — must reach TERMINADO.

        After WU-3: PAX_NINOS → MONTO_VALOR (no NUMERO_TICKET).
        After WU-5: MONTO_ABONO auto-calculates neto when possible → PARTICIPANTE_ROL.
        For this test, service 3 has neto_adulto=None → fallback to MONTO_NETO.
        """
        ctx = ContextoVenta()

        # TIPO_RESERVA
        s = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert s.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA
        ctx = s.contexto

        # PUNTO_DE_VENTA
        s = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s.nuevo_estado == EstadoFSM.DESTINO
        ctx = s.contexto

        # DESTINO — enter number then confirm (service 3 has no neto)
        s = fsm.procesar(EstadoFSM.DESTINO, "3", ctx)
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

        # PAX_NINOS → MONTO_VALOR directly (NUMERO_TICKET removed in WU-3)
        s = fsm.procesar(EstadoFSM.PAX_NINOS, "0", ctx)
        assert s.nuevo_estado == EstadoFSM.MONTO_VALOR
        ctx = s.contexto

        # MONTO_VALOR
        s = fsm.procesar(EstadoFSM.MONTO_VALOR, "500.000", ctx)
        assert s.nuevo_estado == EstadoFSM.MONTO_ABONO
        ctx = s.contexto

        # MONTO_ABONO → MONTO_NETO (service 3 has no neto_adulto — fallback)
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
