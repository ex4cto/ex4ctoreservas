"""Tests for the pure FSM — Telegram-free, import-only garay.aplicacion.tiquetera.fsm."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import (
    EstadoFSM,
    FSMTiquetera,
    _es_sin_hotel,
    _formatear_monto,
    _parsear_monto,
)
from garay.dominio.ventas.contexto import ContextoVenta

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
    def test_destino_numero_agrega(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        s1 = fsm.procesar(EstadoFSM.DESTINO, "1", ctx)
        assert s1.nuevo_estado == EstadoFSM.DESTINO
        assert 1 in s1.contexto.destinos_numeros

    def test_destino_multiples_numeros(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
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

    def test_fecha_valida_avanza_a_pax_adultos(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS


class TestPax:
    def test_adultos_invalido_devuelve_error(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS

    def test_pax_ninos_avanza_a_monto_valor(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
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

    def test_fecha_dd_mm_yyyy_sigue_funcionando(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
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

    def test_neto_supera_valor_venta_vuelve_a_monto_valor(self, fsm: FSMTiquetera) -> None:
        # neto auto-calculated (100000) > valor_venta (50000) → MONTO_VALOR with error
        ctx = ContextoVenta(destinos_numeros=[1], adultos=1, ninos=0, valor=Decimal("50000"))
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.MONTO_VALOR
        assert "$50.000" in salida.mensaje or "$100.000" in salida.mensaje


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
    """Fix 3: Editar from CONFIRMACION now goes to EDITAR_SELECTOR, not TIPO_RESERVA."""

    def test_confirmacion_editar_va_a_editar_selector(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✏️ Editar", ctx)
        assert salida.nuevo_estado == EstadoFSM.EDITAR_SELECTOR
        assert len(salida.opciones) > 0

    def test_confirmacion_confirmar_con_ctx_vacio_bloquea(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """With an empty context, confirmation must stay blocked at CONFIRMACION."""
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_confirmacion_cancelar_cancela(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "❌ Cancelar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CANCELADO


class TestMetodoInput:
    """WU-6: METODO_INPUT is the first state returned by iniciar()."""

    def test_metodo_input_manual_avanza_a_tipo_reserva(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.METODO_INPUT, "Manual", ctx)
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA

    def test_metodo_input_foto_avanza_a_esperando_foto(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.METODO_INPUT, "Foto", ctx)
        assert salida.nuevo_estado == EstadoFSM.ESPERANDO_FOTO

    def test_esperando_foto_rechaza_texto(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.ESPERANDO_FOTO, "hola", ctx)
        assert salida.nuevo_estado == EstadoFSM.ESPERANDO_FOTO

    def test_metodo_input_invalido_repite(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
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
    def test_confirmacion_confirmar_con_ctx_vacio_bloquea(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """With an empty context, confirmation must stay blocked at CONFIRMACION."""
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION


class TestCancelar:
    def test_cancelar_desde_cualquier_estado(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
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

    def test_procesar_foto_auto_avanza_cliente_nombre_prefilled(self, fsm: FSMTiquetera) -> None:
        """ctx with cliente_nombre set: after DESTINO→confirmar reaches CLIENTE_TELEFONO."""
        ctx = ContextoVenta(destinos_numeros=[1], cliente_nombre="Juan")
        salida = fsm.procesar_foto(EstadoFSM.DESTINO, "confirmar", ctx)
        # DESTINO→confirmar → CLIENTE_NOMBRE → auto-advance to CLIENTE_TELEFONO
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_TELEFONO
        assert salida.contexto.cliente_nombre == "Juan"

    def test_procesar_foto_no_avanza_sin_valor(self, fsm: FSMTiquetera) -> None:
        """ctx without cliente_nombre: stays at CLIENTE_NOMBRE."""
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm.procesar_foto(EstadoFSM.DESTINO, "confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE

    def test_procesar_foto_pax_adultos_cero_no_avanza(self, fsm: FSMTiquetera) -> None:
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

    def test_procesar_foto_pax_adultos_uno_avanza(self, fsm: FSMTiquetera) -> None:
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


# ─── Fix 1: destino mensaje sin instruccion cuando hay seleccion ─────────────


class TestDestinoMensaje:
    """Fix 1: instruction line hidden when tours already selected."""

    def test_destinos_mensaje_sin_seleccion_muestra_instruccion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        # No tours selected → instruction line must appear
        salida = fsm.procesar(EstadoFSM.DESTINO, "9999", ctx)
        assert "Ingresá el número del tour" in salida.mensaje

    def test_destinos_mensaje_con_seleccion_omite_instruccion(self, fsm: FSMTiquetera) -> None:
        # Tours already selected → instruction line must NOT appear, only "Seleccionados:"
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm.procesar(EstadoFSM.DESTINO, "2", ctx)
        assert "Ingresá el número del tour" not in salida.mensaje
        assert "Seleccionados:" in salida.mensaje
        assert "Agregá más" in salida.mensaje


# ─── Fix 2: hotel skip detection flexible ────────────────────────────────────


class TestEsSinHotel:
    """Fix 2: _es_sin_hotel covers flexible natural-language inputs."""

    def test_exacto_no(self) -> None:
        assert _es_sin_hotel("no") is True

    def test_exacto_ninguno(self) -> None:
        assert _es_sin_hotel("ninguno") is True

    def test_frase_corta_no_estoy(self) -> None:
        assert _es_sin_hotel("no estoy en ningún hotel") is True

    def test_frase_no_tengo(self) -> None:
        assert _es_sin_hotel("no tengo hotel") is True

    def test_hotel_nombre_real_no_confunde(self) -> None:
        # A real hotel name that starts with "Hotel No" should NOT match
        assert _es_sin_hotel("Hotel Novotel Centro") is False

    def test_nombre_largo_con_no_no_confunde(self) -> None:
        # Long sentence with "no" in it that is clearly a hotel name should not match
        assert _es_sin_hotel("Estamos en el Novotel cerca del centro comercial gran hotel") is False

    def test_typo_nignuno(self) -> None:
        assert _es_sin_hotel("nignuno") is True

    def test_typo_nignuna(self) -> None:
        assert _es_sin_hotel("nignuna") is True

    def test_typo_sin_htel(self) -> None:
        assert _es_sin_hotel("sin htel") is True

    def test_hotel_real_no_confunde_con_fuzzy(self) -> None:
        # Short real hotel names must not false-positive
        assert _es_sin_hotel("sol") is False
        assert _es_sin_hotel("ibis") is False


class TestHotelSkipFlexible:
    """Fix 2: FSM accepts flexible no-hotel phrases."""

    def test_hotel_frase_completa_sin_hotel(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "no estoy en ningún hotel", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert salida.contexto.sin_hotel is True

    def test_hotel_frase_no_tengo(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "no tengo hotel", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_hotel_ninguna(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "ninguna", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_hotel_nombre_real_no_se_confunde(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "Hotel Novotel Centro", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HABITACION


# ─── Fix 3: EDITAR_SELECTOR ──────────────────────────────────────────────────


class TestEditarSelector:
    """Fix 3: field-by-field edit mode from CONFIRMACION."""

    def test_editar_selector_aparece_desde_confirmacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✏️ Editar", ctx)
        assert salida.nuevo_estado == EstadoFSM.EDITAR_SELECTOR
        assert len(salida.opciones) > 0
        assert "Cliente" in salida.opciones

    def test_editar_selector_campo_invalido_repite(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "CampoQueNoExiste", ctx)
        assert salida.nuevo_estado == EstadoFSM.EDITAR_SELECTOR

    def test_editar_selector_cliente_va_a_cliente_nombre(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Cliente", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE
        assert salida.contexto.modo_edicion is True

    def test_editar_cliente_nombre_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        # modo_edicion=True → after editing a field, return to CONFIRMACION
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.CLIENTE_NOMBRE, "Nuevo Nombre", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.cliente_nombre == "Nuevo Nombre"

    def test_editar_hotel_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "Grand Hyatt", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_modo_edicion_se_resetea_tras_editar(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.CLIENTE_NOMBRE, "Otro", ctx)
        assert salida.contexto.modo_edicion is False

    def test_editar_tipo_reserva_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_editar_fecha_salida_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_editar_monto_abono_vuelve_a_confirmacion_cuando_neto_conocido(
        self, fsm: FSMTiquetera
    ) -> None:
        # When neto can be auto-calculated and modo_edicion=True, go to CONFIRMACION
        ctx = ContextoVenta(destinos_numeros=[1], adultos=1, ninos=0, modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_editar_participante_rol_ambos_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION


# ─── Fix 4: formateo de montos ───────────────────────────────────────────────


class TestFormatearMonto:
    """Fix 4: _formatear_monto uses dot as thousands separator."""

    def test_formatear_monto_entero_grande(self) -> None:
        assert _formatear_monto(Decimal("200000")) == "$200.000"

    def test_formatear_monto_none(self) -> None:
        assert _formatear_monto(None) == "—"

    def test_formatear_monto_pequeño(self) -> None:
        assert _formatear_monto(Decimal("500")) == "$500"

    def test_formatear_monto_millon(self) -> None:
        assert _formatear_monto(Decimal("1000000")) == "$1.000.000"


class TestResumenMontos:
    """Fix 4: summary uses _formatear_monto for valor/abono/neto."""

    def test_resumen_muestra_montos_formateados(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(
            destinos_numeros=[1],
            rol_registrante="ambos",
            valor=Decimal("200000"),
            abono=Decimal("50000"),
            neto=Decimal("100000"),
        )
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert "200.000" in salida.mensaje
        assert "50.000" in salida.mensaje
        assert "100.000" in salida.mensaje


class TestParsearMonto:
    """_parsear_monto must scale plain numbers < 1000 by x1000 (Colombian miles notation)."""

    def test_plain_hundreds_scaled(self) -> None:
        assert _parsear_monto("500") == Decimal("500000")

    def test_plain_two_digits_scaled(self) -> None:
        assert _parsear_monto("50") == Decimal("50000")

    def test_dot_thousands_not_scaled(self) -> None:
        assert _parsear_monto("500.000") == Decimal("500000")

    def test_large_number_not_scaled(self) -> None:
        assert _parsear_monto("1800000") == Decimal("1800000")

    def test_dot_thousands_large_not_scaled(self) -> None:
        assert _parsear_monto("1.800.000") == Decimal("1800000")


# ─── foto_modo: jump to CONFIRMACION after PUNTO_DE_VENTA ────────────────────


class TestFotoModo:
    """foto_modo=True causes _handle_punto_de_venta to skip DESTINO and go to PARTICIPANTE_ROL."""

    def test_estados_foto_avanzar_no_incluye_monto_valor_ni_monto_abono(self) -> None:
        """MONTO_VALOR and MONTO_ABONO must NOT be in _ESTADOS_FOTO_AVANZAR.

        _handle_monto_abono can loop back to itself (abono > neto path) or to
        MONTO_VALOR (neto > valor path). Including them in the frozenset would
        create an infinite loop in procesar_foto.
        """
        from garay.aplicacion.tiquetera.fsm import _ESTADOS_FOTO_AVANZAR

        assert EstadoFSM.MONTO_VALOR not in _ESTADOS_FOTO_AVANZAR
        assert EstadoFSM.MONTO_ABONO not in _ESTADOS_FOTO_AVANZAR

    def test_foto_modo_salta_a_participante_rol_despues_de_punto_de_venta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """With foto_modo=True, _handle_punto_de_venta jumps to PARTICIPANTE_ROL."""
        ctx.foto_modo = True
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_foto_modo_false_after_punto_de_venta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """foto_modo is reset to False in the returned context."""
        ctx.foto_modo = True
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.contexto.foto_modo is False

    def test_foto_modo_computa_neto_cuando_datos_disponibles(
        self, fsm: FSMTiquetera
    ) -> None:
        """When foto_modo=True and abono/adultos are set, neto is auto-computed."""
        ctx = ContextoVenta(
            foto_modo=True,
            abono=Decimal("50000"),
            adultos=2,
            ninos=0,
            destinos_numeros=[1],  # Tour Playa Blanca: neto_adulto=100000
        )
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.neto == Decimal("200000")  # 100000 * 2 adultos

    def test_handle_destino_recomputa_neto_en_modo_edicion(
        self, fsm: FSMTiquetera
    ) -> None:
        """Editing destinations recomputes neto when modo_edicion=True and abono is set."""
        ctx = ContextoVenta(
            modo_edicion=True,
            abono=Decimal("50000"),
            adultos=2,
            ninos=0,
        )
        # First: select destination 1
        salida = fsm.procesar(EstadoFSM.DESTINO, "1", ctx)
        ctx2 = salida.contexto
        # Now confirm with modo_edicion=True
        ctx2.modo_edicion = True
        salida2 = fsm.procesar(EstadoFSM.DESTINO, "confirmar", ctx2)
        assert salida2.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida2.contexto.neto == Decimal("200000")  # 100000 * 2 adultos

    def test_zero_stays_zero(self) -> None:
        assert _parsear_monto("0") == Decimal("0")

    def test_invalid_returns_none(self) -> None:
        assert _parsear_monto("abc") is None


# ─── Change 1: procesar_foto respects modo_edicion ───────────────────────────


class TestProcesarFotoModoEdicion:
    """Change 1: procesar_foto must NOT auto-advance when modo_edicion=True."""

    def test_procesar_foto_no_avanza_cuando_modo_edicion(self, fsm: FSMTiquetera) -> None:
        """With modo_edicion=True, procesar_foto stops at the target state even when
        the next state also has a pre-filled value (telefono pre-filled)."""
        # Full context — all ESTADOS_FOTO_AVANZAR values are set
        ctx = ContextoVenta(
            destinos_numeros=[1],
            cliente_nombre="Juan",
            cliente_telefono="300111222",
            cliente_hotel="Grand",
            cliente_habitacion="101",
            fecha_salida=datetime.datetime(2026, 12, 25, 10, 0),
            adultos=2,
            ninos=0,
            modo_edicion=True,
        )
        # Simulate: user selected "Cliente" in EDITAR_SELECTOR → CLIENTE_NOMBRE with modo_edicion
        # Now user types the new name — procesar_foto is called with EDITAR_SELECTOR
        salida = fsm.procesar_foto(EstadoFSM.EDITAR_SELECTOR, "Cliente", ctx)
        # _handle_editar_selector sets modo_edicion=True and returns CLIENTE_NOMBRE.
        # Without the fix, procesar_foto would auto-advance through pre-filled states.
        # With the fix it must stop at CLIENTE_NOMBRE.
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE
        assert salida.contexto.modo_edicion is True

    def test_procesar_foto_avanza_normalmente_sin_modo_edicion(self, fsm: FSMTiquetera) -> None:
        """Regression: without modo_edicion auto-advance still works for photo flow."""
        ctx = ContextoVenta(
            destinos_numeros=[1],
            cliente_nombre="Juan",
            cliente_telefono=None,
        )
        salida = fsm.procesar_foto(EstadoFSM.DESTINO, "confirmar", ctx)
        # CLIENTE_NOMBRE has value, so it auto-advances to CLIENTE_TELEFONO (no value → stops)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_TELEFONO


# ─── Change 2: Adultos/Niños edit covers both fields ─────────────────────────


class TestEditarAdultosNinos:
    """Change 2: editing 'Adultos/Niños' must prompt for niños after adultos."""

    def test_editar_adultos_ninos_pide_ninos_tras_adultos(self, fsm: FSMTiquetera) -> None:
        """When modo_edicion=True, _handle_pax_adultos must go to PAX_NINOS, not CONFIRMACION."""
        ctx = ContextoVenta(modo_edicion=True, adultos=1, ninos=2)
        salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "3", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_NINOS
        assert salida.contexto.adultos == 3
        # modo_edicion must still be True so PAX_NINOS knows to return to CONFIRMACION
        assert salida.contexto.modo_edicion is True

    def test_editar_adultos_ninos_completo_va_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        """After adultos → niños, _handle_pax_ninos clears modo_edicion and goes to CONFIRMACION."""
        ctx = ContextoVenta(modo_edicion=True, adultos=1, ninos=2)
        # Step 1: edit adultos
        salida1 = fsm.procesar(EstadoFSM.PAX_ADULTOS, "3", ctx)
        assert salida1.nuevo_estado == EstadoFSM.PAX_NINOS
        # Step 2: edit niños
        salida2 = fsm.procesar(EstadoFSM.PAX_NINOS, "1", salida1.contexto)
        assert salida2.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida2.contexto.adultos == 3
        assert salida2.contexto.ninos == 1
        assert salida2.contexto.modo_edicion is False


# ─── Change 3: Habitación en _CAMPOS_EDITABLES ───────────────────────────────


class TestHabitacionEditable:
    """Change 3: 'Habitación' must appear in _CAMPOS_EDITABLES."""

    def test_habitacion_aparece_en_campos_editables(self, fsm: FSMTiquetera) -> None:
        from garay.aplicacion.tiquetera.fsm import _CAMPOS_EDITABLES

        target_states = {estado for _, estado in _CAMPOS_EDITABLES}
        assert EstadoFSM.CLIENTE_HABITACION in target_states

    def test_editar_habitacion_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        """With modo_edicion=True, CLIENTE_HABITACION returns to CONFIRMACION."""
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.CLIENTE_HABITACION, "202", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.cliente_habitacion == "202"

    def test_editar_selector_habitacion_navega_correctamente(self, fsm: FSMTiquetera) -> None:
        """Selecting 'Habitación' from EDITAR_SELECTOR navigates to CLIENTE_HABITACION."""
        ctx = ContextoVenta()
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Habitación", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HABITACION
        assert salida.contexto.modo_edicion is True


# ─── Change 4: EDITAR_VENDEDOR / EDITAR_CERRADOR states ─────────────────────


class TestEditarParticipantes:
    """Change 4: new FSM states for editing participant names directly."""

    def test_editar_participantes_mapea_a_editar_vendedor(self, fsm: FSMTiquetera) -> None:
        """'Participantes' in EDITAR_SELECTOR must go to EDITAR_VENDEDOR (not PARTICIPANTE_ROL)."""
        from garay.aplicacion.tiquetera.fsm import _CAMPOS_EDITABLES

        campos_map = {label: estado for label, estado in _CAMPOS_EDITABLES}
        assert campos_map.get("Participantes") == EstadoFSM.EDITAR_VENDEDOR

    def test_editar_participantes_ambos_pide_vendedor_luego_cerrador(
        self, fsm: FSMTiquetera
    ) -> None:
        """rol='ambos': EDITAR_VENDEDOR → EDITAR_CERRADOR → CONFIRMACION."""
        ctx = ContextoVenta(rol_registrante="ambos", modo_edicion=True)
        # Step 1: enter vendor name
        salida1 = fsm.procesar(EstadoFSM.EDITAR_VENDEDOR, "Maria", ctx)
        assert salida1.nuevo_estado == EstadoFSM.EDITAR_CERRADOR
        assert salida1.contexto.vendedor_nombre == "Maria"
        # Step 2: enter closer name
        salida2 = fsm.procesar(EstadoFSM.EDITAR_CERRADOR, "Pedro", salida1.contexto)
        assert salida2.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida2.contexto.cerrador_nombre == "Pedro"
        assert salida2.contexto.modo_edicion is False

    def test_editar_participantes_solo_vendedor_va_directo_a_confirmacion(
        self, fsm: FSMTiquetera
    ) -> None:
        """rol='vendedor': EDITAR_VENDEDOR → CONFIRMACION (no cerrador step)."""
        ctx = ContextoVenta(rol_registrante="vendedor", modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.EDITAR_VENDEDOR, "Carlos", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.vendedor_nombre == "Carlos"
        assert salida.contexto.modo_edicion is False

    def test_editar_participantes_cerrador_guarda_en_vendedor_nombre(
        self, fsm: FSMTiquetera
    ) -> None:
        """rol='cerrador': EDITAR_VENDEDOR stores into vendedor_nombre → CONFIRMACION."""
        ctx = ContextoVenta(rol_registrante="cerrador", modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.EDITAR_VENDEDOR, "Ana", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.vendedor_nombre == "Ana"
        assert salida.contexto.modo_edicion is False

    def test_habitacion_en_campos_editables_no_es_participante_rol(
        self, fsm: FSMTiquetera
    ) -> None:
        """After change 4, 'Participantes' maps to EDITAR_VENDEDOR, NOT PARTICIPANTE_ROL."""
        from garay.aplicacion.tiquetera.fsm import _CAMPOS_EDITABLES

        campos_map = {label: estado for label, estado in _CAMPOS_EDITABLES}
        assert campos_map.get("Participantes") != EstadoFSM.PARTICIPANTE_ROL

    def test_editar_vendedor_estado_existe_en_enum(self) -> None:
        """EstadoFSM.EDITAR_VENDEDOR and EDITAR_CERRADOR must exist."""
        assert EstadoFSM.EDITAR_VENDEDOR == "editar_vendedor"
        assert EstadoFSM.EDITAR_CERRADOR == "editar_cerrador"

    def test_negative_returns_none(self) -> None:
        assert _parsear_monto("-500") is None


# ─── foto_modo: salta a PARTICIPANTE_ROL (no CONFIRMACION) ──────────────────


class TestFotoModoSaltaParticipanteRol:
    """Cambio 3: foto_modo=True must route to PARTICIPANTE_ROL after PUNTO_DE_VENTA."""

    def test_foto_modo_salta_a_participante_rol_no_confirmacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """Con foto_modo=True, _handle_punto_de_venta va a PARTICIPANTE_ROL, no CONFIRMACION."""
        ctx.foto_modo = True
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_foto_modo_opciones_participante_rol(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """La salida debe tener las opciones de rol."""
        ctx.foto_modo = True
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert "Ambos" in salida.opciones

    def test_foto_modo_false_se_resetea(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """foto_modo se resetea a False en el contexto retornado."""
        ctx.foto_modo = True
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.contexto.foto_modo is False


# ─── Validación en _handle_confirmacion ──────────────────────────────────────


@pytest.fixture()
def ctx_completo() -> ContextoVenta:
    """A ContextoVenta with all required fields filled (tipo INTERNO)."""
    return ContextoVenta(
        cliente_nombre="Ana García",
        cliente_telefono="3001234567",
        cliente_hotel="Hotel Test",
        cliente_habitacion="101",
        fecha_salida=datetime.datetime(2026, 8, 1, 8, 0),
        adultos=2,
        ninos=1,
        destinos_numeros=[1],
        valor=Decimal("260000"),
        abono=Decimal("130000"),
        tipo_cliente="INTERNO",
        punto_de_venta_nombre="Hotel Test",
        rol_registrante="ambos",
        neto=Decimal("180000"),
    )


class TestValidarDatosConfirmacion:
    def test_ctx_completo_no_tiene_faltantes(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        """Un contexto con todos los campos rellenos no bloquea confirmacion."""
        assert fsm._validar_datos_confirmacion(ctx_completo) == []

    def test_falta_cliente_nombre(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_nombre = None
        assert "Nombre del cliente" in fsm._validar_datos_confirmacion(ctx_completo)

    def test_falta_telefono(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_telefono = None
        assert "Teléfono" in fsm._validar_datos_confirmacion(ctx_completo)

    def test_hotel_habitacion_obligatorios_solo_para_interno(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.tipo_cliente = "EXTERNO"
        ctx_completo.cliente_hotel = None
        ctx_completo.cliente_habitacion = None
        faltantes = fsm._validar_datos_confirmacion(ctx_completo)
        assert "Hotel" not in faltantes
        assert "Habitación" not in faltantes

    def test_hotel_obligatorio_para_interno(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.tipo_cliente = "INTERNO"
        ctx_completo.cliente_hotel = None
        assert "Hotel" in fsm._validar_datos_confirmacion(ctx_completo)

    def test_habitacion_obligatoria_para_interno(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.tipo_cliente = "INTERNO"
        ctx_completo.cliente_habitacion = None
        assert "Habitación" in fsm._validar_datos_confirmacion(ctx_completo)

    def test_ninos_cero_es_valido(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.ninos = 0
        assert "Niños" not in " ".join(fsm._validar_datos_confirmacion(ctx_completo))

    def test_ninos_none_falla(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.ninos = None
        faltantes = fsm._validar_datos_confirmacion(ctx_completo)
        assert any("iños" in f for f in faltantes)

    def test_abono_cero_es_valido(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.abono = Decimal("0")
        assert "Abono" not in fsm._validar_datos_confirmacion(ctx_completo)

    def test_confirmacion_bloqueada_si_faltan_datos(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_nombre = None
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx_completo)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert "Nombre del cliente" in salida.mensaje

    def test_confirmacion_procede_si_datos_completos(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx_completo)
        assert salida.nuevo_estado == EstadoFSM.TERMINADO


class TestEditarMensajesConValorActual:
    """_handle_editar_selector shows current ctx value in the prompt."""

    def test_editar_nombre_muestra_valor_actual(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_nombre = "Juan Pérez"
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Cliente", ctx_completo)
        assert "Juan Pérez" in salida.mensaje

    def test_editar_telefono_muestra_valor_actual(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_telefono = "3001234567"
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Teléfono", ctx_completo)
        assert "3001234567" in salida.mensaje

    def test_editar_hotel_muestra_valor_actual(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_hotel = "Hotel Caribe"
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Hotel", ctx_completo)
        assert "Hotel Caribe" in salida.mensaje

    def test_editar_hotel_sin_hotel_muestra_sin_hotel(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.sin_hotel = True
        ctx_completo.cliente_hotel = None
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Hotel", ctx_completo)
        assert "Sin hotel" in salida.mensaje

    def test_editar_habitacion_muestra_valor_actual(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_habitacion = "304"
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Habitación", ctx_completo)
        assert "304" in salida.mensaje

    def test_editar_fecha_muestra_valor_actual(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        import datetime
        ctx_completo.fecha_salida = datetime.datetime(2026, 7, 25, 9, 0)
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Fecha", ctx_completo)
        assert "25/07/2026" in salida.mensaje

    def test_editar_adultos_muestra_ambos_valores(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.adultos = 3
        ctx_completo.ninos = 1
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Adultos/Niños", ctx_completo)
        assert "3" in salida.mensaje
        assert "1" in salida.mensaje

    def test_editar_valor_muestra_monto_formateado(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        from decimal import Decimal
        ctx_completo.valor = Decimal("260000")
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Monto valor", ctx_completo)
        assert "$260.000" in salida.mensaje

    def test_editar_abono_muestra_monto_formateado(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        from decimal import Decimal
        ctx_completo.abono = Decimal("130000")
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Abono", ctx_completo)
        assert "$130.000" in salida.mensaje


class TestNetoRecalculoEnEdicion:
    """Neto must recalculate from catalog whenever destino or pax changes in edit mode."""

    def test_editar_destino_recalcula_neto_aunque_ya_estaba_seteado(
        self, fsm: FSMTiquetera
    ) -> None:
        # neto stale from a previous calculation; after confirming destino edit it must update
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=2,
            ninos=0,
            neto=Decimal("999999"),
            modo_edicion=True,
        )
        salida = fsm.procesar(EstadoFSM.DESTINO, "confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        # Service 1: 100000 x 2 adultos = 200000
        assert salida.contexto.neto == Decimal("200000")

    def test_editar_pax_recalcula_neto_aunque_ya_estaba_seteado(
        self, fsm: FSMTiquetera
    ) -> None:
        # adultos went from 1 → 2; neto should update from 100000 to 200000
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=2,
            neto=Decimal("100000"),
            modo_edicion=True,
        )
        salida = fsm.procesar(EstadoFSM.PAX_NINOS, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        # Service 1: 100000 x 2 adultos = 200000
        assert salida.contexto.neto == Decimal("200000")

    def test_foto_modo_recalcula_neto_desde_catalogo(self, fsm: FSMTiquetera) -> None:
        # IA extracted a wrong neto; catalog must override it
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=2,
            ninos=0,
            abono=Decimal("0"),
            neto=Decimal("999999"),
            foto_modo=True,
        )
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        # Service 1: 100000 x 2 adultos = 200000
        assert salida.contexto.neto == Decimal("200000")
