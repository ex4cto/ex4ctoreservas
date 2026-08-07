"""FSM tests for per-tour date capture (Slice 2 — fecha-por-tour).

Covers:
  - Single-tour: one FECHA_SALIDA prompt with existing text → PAX_ADULTOS.
  - Multi-tour: loop stays in FECHA_SALIDA until every tour has a date,
    then advances to PAX_ADULTOS with fecha_salida == min.
  - Photo auto-advance: stops at FECHA_SALIDA when tours still lack dates;
    advances through when fecha_salida is already set.
  - Edit flow: clearing fechas_por_servicio on Fecha edit, re-running loop.
  - Single-tour edit parity.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta
from garay.mensajes.catalogo import obtener_mensaje

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SERVICIOS_2TOURS: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ"),
    (2, "Tour Isla", Decimal("150000"), None, "ISLAS"),
    (3, "City Tour", None, None, "ISLAS"),
]
PUNTOS_TEST: list[str] = ["Marie Real"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_2TOURS, puntos_venta=PUNTOS_TEST)


def _ctx_single_tour(**overrides: object) -> ContextoVenta:
    """ContextoVenta ready to enter FECHA_SALIDA with one tour selected."""
    defaults: dict[str, object] = {
        "destinos_numeros": [1],
        "destinos_nombres": ["Tour Playa Blanca"],
    }
    defaults.update(overrides)
    return ContextoVenta(**defaults)  # type: ignore[arg-type]


def _ctx_two_tours(**overrides: object) -> ContextoVenta:
    """ContextoVenta ready to enter FECHA_SALIDA with two tours selected."""
    defaults: dict[str, object] = {
        "destinos_numeros": [1, 2],
        "destinos_nombres": ["Tour Playa Blanca", "Tour Isla"],
    }
    defaults.update(overrides)
    return ContextoVenta(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T-S1: Single-tour — prompt text is the EXACT existing catalog text
# ---------------------------------------------------------------------------


class TestSingleTourDateCapture:
    def test_single_tour_prompt_text_is_existing_catalog_key(self, fsm: FSMTiquetera) -> None:
        """The message shown for FECHA_SALIDA must be the unmodified catalog text."""
        ctx = _ctx_single_tour()
        # Simulate transition into FECHA_SALIDA from CLIENTE_HOTEL (sin hotel path)
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "no", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert salida.mensaje == obtener_mensaje("pregunta_fecha_salida")

    def test_single_tour_advances_to_pax_adultos(self, fsm: FSMTiquetera) -> None:
        """After entering the date for the sole tour, advance to PAX_ADULTOS."""
        ctx = _ctx_single_tour()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS

    def test_single_tour_fecha_salida_set_to_entered_date(self, fsm: FSMTiquetera) -> None:
        """ctx.fecha_salida must equal the entered date."""
        ctx = _ctx_single_tour()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)
        assert salida.contexto.fecha_salida == datetime.datetime(2026, 12, 25)

    def test_single_tour_fechas_por_servicio_has_one_entry(self, fsm: FSMTiquetera) -> None:
        """fechas_por_servicio must have exactly one entry keyed by tour numero."""
        ctx = _ctx_single_tour()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)
        assert len(salida.contexto.fechas_por_servicio) == 1
        assert 1 in salida.contexto.fechas_por_servicio
        assert salida.contexto.fechas_por_servicio[1] == datetime.datetime(2026, 12, 25)

    def test_single_tour_fecha_salida_equals_only_entry(self, fsm: FSMTiquetera) -> None:
        """fecha_salida == min(fechas_por_servicio.values()) for a single tour."""
        ctx = _ctx_single_tour()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "15/08/2026 10:30", ctx)
        expected = datetime.datetime(2026, 8, 15, 10, 30)
        assert salida.contexto.fechas_por_servicio[1] == expected
        assert salida.contexto.fecha_salida == expected


# ---------------------------------------------------------------------------
# T-M1: Multi-tour — loop stays in FECHA_SALIDA until all tours dated
# ---------------------------------------------------------------------------


class TestMultiTourDateLoop:
    def test_first_fecha_stays_in_fecha_salida(self, fsm: FSMTiquetera) -> None:
        """With 2 tours, entering the first date keeps state at FECHA_SALIDA."""
        ctx = _ctx_two_tours()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "20/12/2026", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_second_fecha_advances_to_pax_adultos(self, fsm: FSMTiquetera) -> None:
        """After both dates are entered, advance to PAX_ADULTOS."""
        ctx = _ctx_two_tours()
        # First date for tour 1
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "20/12/2026", ctx)
        assert s1.nuevo_estado == EstadoFSM.FECHA_SALIDA
        # Second date for tour 2
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "22/12/2026", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.PAX_ADULTOS

    def test_multi_tour_fecha_salida_is_min(self, fsm: FSMTiquetera) -> None:
        """ctx.fecha_salida == min of all per-tour dates."""
        ctx = _ctx_two_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "22/12/2026", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "20/12/2026", s1.contexto)
        assert s2.contexto.fecha_salida == datetime.datetime(2026, 12, 20)

    def test_multi_tour_fechas_por_servicio_has_two_entries(self, fsm: FSMTiquetera) -> None:
        """fechas_por_servicio must have entries for both tours."""
        ctx = _ctx_two_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "20/12/2026", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "22/12/2026", s1.contexto)
        fps = s2.contexto.fechas_por_servicio
        assert 1 in fps
        assert 2 in fps
        assert fps[1] == datetime.datetime(2026, 12, 20)
        assert fps[2] == datetime.datetime(2026, 12, 22)

    def test_second_prompt_names_the_tour(self, fsm: FSMTiquetera) -> None:
        """The second FECHA_SALIDA prompt must contain the tour name."""
        ctx = _ctx_two_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "20/12/2026", ctx)
        # The message for the second prompt should name "Tour Isla"
        assert "Tour Isla" in s1.mensaje

    def test_multi_tour_first_prompt_from_habitacion_names_first_tour(
        self, fsm: FSMTiquetera
    ) -> None:
        """Entry to FECHA_SALIDA from CLIENTE_HABITACION must name the first tour."""
        ctx = _ctx_two_tours()
        salida = fsm.procesar(EstadoFSM.CLIENTE_HABITACION, "101", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert "Tour Playa Blanca" in salida.mensaje

    def test_multi_tour_first_prompt_from_sin_hotel_names_first_tour(
        self, fsm: FSMTiquetera
    ) -> None:
        """Entry to FECHA_SALIDA from CLIENTE_HOTEL (sin hotel) must name the first tour."""
        ctx = _ctx_two_tours()
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "no", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert "Tour Playa Blanca" in salida.mensaje

    def test_invalid_date_stays_in_fecha_salida_multi(self, fsm: FSMTiquetera) -> None:
        """Invalid date in multi-tour loop stays at FECHA_SALIDA."""
        ctx = _ctx_two_tours()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "not-a-date", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA


# ---------------------------------------------------------------------------
# T-P1: Photo auto-advance — FECHA_SALIDA behavior
# ---------------------------------------------------------------------------


class TestPhotoAutoAdvanceFechaSalida:
    def test_photo_stops_at_fecha_salida_when_no_date_prefilled(
        self, fsm: FSMTiquetera
    ) -> None:
        """procesar_foto stops at FECHA_SALIDA when no date is prefilled (multi-tour)."""
        ctx = _ctx_two_tours(
            cliente_nombre="Juan",
            cliente_telefono="300",
            sin_hotel=True,
        )
        # No fecha_salida set → auto-advance should STOP at FECHA_SALIDA
        salida = fsm.procesar_foto(EstadoFSM.CLIENTE_HABITACION, "101", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_photo_advances_through_fecha_salida_when_all_dates_known(
        self, fsm: FSMTiquetera
    ) -> None:
        """procesar_foto advances through FECHA_SALIDA when fecha_salida is already set."""
        ctx = ContextoVenta(
            destinos_numeros=[1],
            destinos_nombres=["Tour Playa Blanca"],
            cliente_nombre="Juan",
            cliente_telefono="300",
            cliente_hotel="Hotel",
            cliente_habitacion="101",
            fecha_salida=datetime.datetime(2026, 12, 25, 10, 0),
            adultos=0,  # stops at PAX_ADULTOS
        )
        salida = fsm.procesar_foto(EstadoFSM.CLIENTE_HABITACION, "101", ctx)
        # Should advance THROUGH FECHA_SALIDA (fecha_salida already set) and stop at PAX_ADULTOS
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS


# ---------------------------------------------------------------------------
# T-E1: Edit flow — Fecha edit clears fechas_por_servicio and re-runs loop
# ---------------------------------------------------------------------------


class TestEditFechaPerTour:
    def test_single_tour_edit_returns_to_confirmacion(self, fsm: FSMTiquetera) -> None:
        """Editing fecha in single-tour mode: one prompt → CONFIRMACION.

        The _handle_editar_selector clears fechas_por_servicio before routing here,
        so the edit starts with an empty map.
        """
        ctx = ContextoVenta(
            destinos_numeros=[1],
            destinos_nombres=["Tour Playa Blanca"],
            fecha_salida=datetime.datetime(2026, 12, 25),
            fechas_por_servicio={},  # cleared by _handle_editar_selector
            modo_edicion=True,
        )
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "10/01/2027", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_single_tour_edit_updates_fecha(self, fsm: FSMTiquetera) -> None:
        """Editing fecha in single-tour: new date stored in both fields.

        The _handle_editar_selector clears fechas_por_servicio before routing here.
        """
        ctx = ContextoVenta(
            destinos_numeros=[1],
            destinos_nombres=["Tour Playa Blanca"],
            fecha_salida=datetime.datetime(2026, 12, 25),
            fechas_por_servicio={},  # cleared by _handle_editar_selector
            modo_edicion=True,
        )
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "10/01/2027", ctx)
        assert salida.contexto.fecha_salida == datetime.datetime(2027, 1, 10)
        assert salida.contexto.fechas_por_servicio[1] == datetime.datetime(2027, 1, 10)

    def test_multi_tour_edit_loop_first_date_stays_in_fecha_salida(
        self, fsm: FSMTiquetera
    ) -> None:
        """Editing fecha with 2 tours: first new date keeps state at FECHA_SALIDA."""
        # Simulate edit after both tours already had dates — fechas cleared on edit entry
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            fecha_salida=datetime.datetime(2026, 12, 20),
            fechas_por_servicio={},  # cleared by edit entry
            modo_edicion=True,
        )
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "05/01/2027", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_multi_tour_edit_loop_second_date_returns_to_confirmacion(
        self, fsm: FSMTiquetera
    ) -> None:
        """After both new dates entered in edit mode, return to CONFIRMACION."""
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            fecha_salida=datetime.datetime(2026, 12, 20),
            fechas_por_servicio={},  # cleared
            modo_edicion=True,
        )
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "05/01/2027", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "07/01/2027", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s2.contexto.fecha_salida == datetime.datetime(2027, 1, 5)

    def test_editar_selector_fecha_clears_fechas_por_servicio(
        self, fsm: FSMTiquetera
    ) -> None:
        """EDITAR_SELECTOR 'Fecha' must clear fechas_por_servicio before entering loop."""
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            fecha_salida=datetime.datetime(2026, 12, 20),
            fechas_por_servicio={
                1: datetime.datetime(2026, 12, 20),
                2: datetime.datetime(2026, 12, 22),
            },
        )
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Fecha", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert salida.contexto.fechas_por_servicio == {}
        assert salida.contexto.modo_edicion is True
