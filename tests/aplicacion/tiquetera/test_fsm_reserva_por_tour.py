"""Tests for Slice 1 — one tour per reservation; multi-tour dormant behind flag.

RED phase: these tests FAIL before the implementation is in place.

Scenarios:
  - One-tour mode (flag False, default):
      * picking a tour in SERVICIO_EN_FAMILIA routes directly to CLIENTE_NOMBRE.
      * the accumulator (DESTINO state) is NOT shown.
  - One-tour mode + modo_edicion:
      * editing "Destinos" and picking a new tour returns to CONFIRMACION (not
        CLIENTE_NOMBRE), with neto recomputed for the new tour.
      * also recomputes fecha_salida from fechas_por_servicio when present.
  - Multi-tour mode (flag True):
      * picking a tour still goes to DESTINO accumulator with "+ Otro tour".
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ"),
    (2, "Tour Isla", Decimal("150000"), None, "ISLAS"),
]
PUNTOS_TEST: list[str] = ["Marie Real"]


@pytest.fixture()
def fsm_one_tour() -> FSMTiquetera:
    """Default FSM — multi_tour_habilitado=False (one-tour mode)."""
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


@pytest.fixture()
def fsm_multi_tour() -> FSMTiquetera:
    """FSM with multi_tour_habilitado=True — preserves accumulator behavior."""
    return FSMTiquetera(
        servicios=SERVICIOS_TEST,
        puntos_venta=PUNTOS_TEST,
        multi_tour_habilitado=True,
    )


def _ctx_baru() -> ContextoVenta:
    """ContextoVenta with BARÚ already selected as the active family."""
    return ContextoVenta(familia_seleccionada="BARÚ")


# ---------------------------------------------------------------------------
# One-tour mode: normal registration path
# ---------------------------------------------------------------------------


class TestOneTourModeNormalPath:
    """Flag False (default): picking a tour skips DESTINO, goes to CLIENTE_NOMBRE."""

    def test_picking_tour_routes_to_cliente_nombre(
        self, fsm_one_tour: FSMTiquetera
    ) -> None:
        ctx = _ctx_baru()
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE

    def test_picking_tour_does_not_show_accumulator(
        self, fsm_one_tour: FSMTiquetera
    ) -> None:
        """DESTINO (accumulator) must NOT appear when multi_tour_habilitado=False."""
        ctx = _ctx_baru()
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado != EstadoFSM.DESTINO

    def test_picking_tour_no_otro_tour_option(
        self, fsm_one_tour: FSMTiquetera
    ) -> None:
        """The '+ Otro tour' option must not appear in one-tour mode."""
        ctx = _ctx_baru()
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        labels: list[str] = []
        if salida.opciones_estructuradas is not None:
            labels = [lbl for lbl, _ in salida.opciones_estructuradas]
        else:
            labels = list(salida.opciones)
        assert not any("Otro tour" in lbl for lbl in labels)

    def test_tour_appended_to_destinos(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_baru()
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert 1 in salida.contexto.destinos_numeros

    def test_mensaje_asks_for_client_name(self, fsm_one_tour: FSMTiquetera) -> None:
        """The message shown must be the client-name prompt, not accumulator text."""
        from garay.mensajes.catalogo import obtener_mensaje

        ctx = _ctx_baru()
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.mensaje == obtener_mensaje("pregunta_cliente_nombre")


# ---------------------------------------------------------------------------
# One-tour mode: modo_edicion path (editing "Destinos" from CONFIRMACION)
# ---------------------------------------------------------------------------


class TestOneTourModeModoEdicion:
    """Flag False: edit path picks ONE tour and returns to CONFIRMACION with neto."""

    def test_edit_tour_returns_to_confirmacion(
        self, fsm_one_tour: FSMTiquetera
    ) -> None:
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            destinos_numeros=[],
            adultos=2,
            ninos=0,
            modo_edicion=True,
        )
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_edit_tour_recomputes_neto(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            destinos_numeros=[],
            adultos=2,
            ninos=0,
            modo_edicion=True,
        )
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        # Service 1: neto_adulto=100000, adultos=2 → neto=200000
        assert salida.contexto.neto == Decimal("200000")

    def test_edit_tour_clears_modo_edicion(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            destinos_numeros=[],
            adultos=2,
            ninos=0,
            modo_edicion=True,
        )
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.contexto.modo_edicion is False

    def test_edit_tour_confirmation_options(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            destinos_numeros=[],
            adultos=2,
            ninos=0,
            modo_edicion=True,
        )
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert "✅ Confirmar" in salida.opciones
        assert "✏️ Editar" in salida.opciones
        assert "❌ Cancelar" in salida.opciones

    def test_edit_tour_recomputes_fecha_salida_from_fechas_por_servicio(
        self, fsm_one_tour: FSMTiquetera
    ) -> None:
        """When fechas_por_servicio has a date for the new tour, fecha_salida is set."""
        fecha = datetime.datetime(2026, 9, 15, 8, 0)
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            destinos_numeros=[],
            adultos=2,
            ninos=0,
            modo_edicion=True,
            fechas_por_servicio={1: fecha},
        )
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.contexto.fecha_salida == fecha

    def test_edit_tour_routes_to_fecha_salida_when_date_missing(
        self, fsm_one_tour: FSMTiquetera
    ) -> None:
        """When fechas_por_servicio is non-empty but the new tour lacks a date,
        route to FECHA_SALIDA to capture it (keeping modo_edicion=True)."""
        fecha = datetime.datetime(2026, 9, 15, 8, 0)
        # Existing sale had tour 2's date; now editing to tour 1 (no date for 1).
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            destinos_numeros=[],
            adultos=2,
            ninos=0,
            modo_edicion=True,
            fechas_por_servicio={2: fecha},  # date for a DIFFERENT tour
        )
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert salida.contexto.modo_edicion is True


# ---------------------------------------------------------------------------
# Multi-tour mode: accumulator preserved (flag True)
# ---------------------------------------------------------------------------


class TestMultiTourModePreserved:
    """Flag True: picking a tour still shows the DESTINO accumulator."""

    def test_picking_tour_routes_to_destino(
        self, fsm_multi_tour: FSMTiquetera
    ) -> None:
        ctx = _ctx_baru()
        salida = fsm_multi_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.DESTINO

    def test_accumulator_shows_otro_tour_option(
        self, fsm_multi_tour: FSMTiquetera
    ) -> None:
        ctx = _ctx_baru()
        salida = fsm_multi_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        labels: list[str] = []
        if salida.opciones_estructuradas is not None:
            labels = [lbl for lbl, _ in salida.opciones_estructuradas]
        else:
            labels = list(salida.opciones)
        assert any("Otro tour" in lbl for lbl in labels)

    def test_accumulator_shows_confirmar_option(
        self, fsm_multi_tour: FSMTiquetera
    ) -> None:
        ctx = _ctx_baru()
        salida = fsm_multi_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        labels: list[str] = []
        if salida.opciones_estructuradas is not None:
            labels = [lbl for lbl, _ in salida.opciones_estructuradas]
        else:
            labels = list(salida.opciones)
        assert any("Confirmar" in lbl for lbl in labels)


# ---------------------------------------------------------------------------
# Slice 2: iniciar_otro_tour
# ---------------------------------------------------------------------------


def _ctx_completo() -> ContextoVenta:
    """A fully-filled ContextoVenta representing a completed first-tour registration."""
    import uuid
    from decimal import Decimal

    return ContextoVenta(
        tipo_cliente=None,  # TipoCliente not imported here — None is fine for preservation tests
        punto_de_venta_nombre="Marie Real",
        canal_origen="WhatsApp",
        cliente_nombre="Juan Perez",
        cliente_telefono="3001234567",
        cliente_email="juan@example.com",
        cliente_identificacion="123456789",
        cliente_tipo_identificacion="CC",
        cliente_hotel="Hotel Caribe",
        cliente_habitacion="101",
        sin_hotel=False,
        # Per-tour fields (must be cleared)
        destinos_numeros=[1],
        destinos_nombres=["Tour Playa Blanca"],
        familia_seleccionada="BARÚ",
        fecha_salida=datetime.datetime(2026, 9, 15, 8, 0),
        fechas_por_servicio={1: datetime.datetime(2026, 9, 15, 8, 0)},
        adultos=2,
        ninos=1,
        valor=Decimal("300000"),
        abono=Decimal("100000"),
        neto=Decimal("200000"),
        numero_fisico="T-001",
        vendedor_nombre="Maria Lopez",
        vendedor_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        cerrador_nombre="Pedro Gomez",
        cerrador_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        referido_nombre="Carlos",
        rol_registrante="ambos",
        modo_edicion=False,
        tour_adicional=False,
    )


class TestIniciarOtroTour:
    """Slice 2 — FSMTiquetera.iniciar_otro_tour resets per-tour fields, keeps client."""

    def test_preserves_cliente_nombre(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.cliente_nombre == "Juan Perez"

    def test_preserves_cliente_telefono(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.cliente_telefono == "3001234567"

    def test_preserves_cliente_email(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.cliente_email == "juan@example.com"

    def test_preserves_cliente_identificacion(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.cliente_identificacion == "123456789"

    def test_preserves_cliente_tipo_identificacion(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.cliente_tipo_identificacion == "CC"

    def test_preserves_cliente_hotel(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.cliente_hotel == "Hotel Caribe"

    def test_preserves_cliente_habitacion(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.cliente_habitacion == "101"

    def test_preserves_sin_hotel(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.sin_hotel is False

    def test_preserves_punto_de_venta_nombre(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.punto_de_venta_nombre == "Marie Real"

    def test_preserves_canal_origen(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.canal_origen == "WhatsApp"

    def test_clears_destinos_numeros(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.destinos_numeros == []

    def test_clears_destinos_nombres(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.destinos_nombres == []

    def test_clears_familia_seleccionada(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.familia_seleccionada is None

    def test_clears_fechas_por_servicio(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.fechas_por_servicio == {}

    def test_clears_fecha_salida(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.fecha_salida is None

    def test_clears_adultos(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.adultos is None

    def test_clears_ninos(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.ninos is None

    def test_clears_valor(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.valor is None

    def test_clears_abono(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.abono is None

    def test_clears_neto(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.neto is None

    def test_clears_numero_fisico(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.numero_fisico is None

    def test_clears_vendedor_nombre(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.vendedor_nombre is None

    def test_clears_vendedor_id(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.vendedor_id is None

    def test_clears_cerrador_nombre(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.cerrador_nombre is None

    def test_clears_cerrador_id(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.cerrador_id is None

    def test_clears_referido_nombre(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.referido_nombre is None

    def test_clears_rol_registrante(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.rol_registrante is None

    def test_sets_tour_adicional_true(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.tour_adicional is True

    def test_clears_modo_edicion(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        ctx.modo_edicion = True
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.contexto.modo_edicion is False

    def test_routes_to_familia(self, fsm_one_tour: FSMTiquetera) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_family_picker_opciones_estructuradas_populated(
        self, fsm_one_tour: FSMTiquetera
    ) -> None:
        ctx = _ctx_completo()
        salida = fsm_one_tour.iniciar_otro_tour(ctx)
        assert salida.opciones_estructuradas is not None
        assert len(salida.opciones_estructuradas) > 0


# ---------------------------------------------------------------------------
# Slice 2: servicio_en_familia with tour_adicional=True
# ---------------------------------------------------------------------------


class TestServicioEnFamiliaTourAdicional:
    """When tour_adicional=True, skip client capture and route to FECHA_SALIDA."""

    def test_tour_adicional_routes_to_fecha_salida(
        self, fsm_one_tour: FSMTiquetera
    ) -> None:
        """tour_adicional=True → FECHA_SALIDA (client already captured)."""
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            cliente_nombre="Juan Perez",
            tour_adicional=True,
        )
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_tour_adicional_destino_appended(
        self, fsm_one_tour: FSMTiquetera
    ) -> None:
        """Tour is still added to destinos_numeros before routing."""
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            cliente_nombre="Juan Perez",
            tour_adicional=True,
        )
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert 1 in salida.contexto.destinos_numeros

    def test_first_tour_still_routes_to_cliente_nombre(
        self, fsm_one_tour: FSMTiquetera
    ) -> None:
        """Regression: tour_adicional=False still routes to CLIENTE_NOMBRE."""
        ctx = ContextoVenta(familia_seleccionada="BARÚ", tour_adicional=False)
        salida = fsm_one_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE

    def test_multi_tour_flag_unchanged(self, fsm_multi_tour: FSMTiquetera) -> None:
        """Regression: multi_tour_habilitado=True still uses accumulator."""
        ctx = ContextoVenta(familia_seleccionada="BARÚ", tour_adicional=True)
        salida = fsm_multi_tour.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.DESTINO
