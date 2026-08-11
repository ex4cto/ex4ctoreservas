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


@pytest.fixture()
def fsm_multi() -> FSMTiquetera:
    """FSM with multi_tour_habilitado=True for multi-tour accumulator tests."""
    return FSMTiquetera(
        servicios=SERVICIOS_2TOURS,
        puntos_venta=PUNTOS_TEST,
        multi_tour_habilitado=True,
    )


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
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Fecha de salida", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert salida.contexto.fechas_por_servicio == {}
        assert salida.contexto.modo_edicion is True


# ---------------------------------------------------------------------------
# T-MIN1: Min proof — last-entered date is minimum (cross-month and cross-year)
# ---------------------------------------------------------------------------


class TestMultiTourMinProof:
    def test_last_entered_is_minimum_across_months(self, fsm: FSMTiquetera) -> None:
        """fecha_salida == min when the LAST-entered date is earlier (different month)."""
        ctx = _ctx_two_tours()
        # Enter tour-1 = 10/01/2027 (January), tour-2 = 25/12/2026 (December — earlier)
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "10/01/2027", ctx)
        assert s1.nuevo_estado == EstadoFSM.FECHA_SALIDA
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.PAX_ADULTOS
        # The LAST-entered date (25/12/2026) is earlier — must be the min
        assert s2.contexto.fecha_salida == datetime.datetime(2026, 12, 25)

    def test_cross_year_min(self, fsm: FSMTiquetera) -> None:
        """fecha_salida == min across two different years."""
        ctx = _ctx_two_tours()
        # Enter tour-1 = 15/03/2027, tour-2 = 20/11/2026 (different year — earlier)
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "15/03/2027", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "20/11/2026", s1.contexto)
        assert s2.contexto.fecha_salida == datetime.datetime(2026, 11, 20)
        assert s2.contexto.fechas_por_servicio[1] == datetime.datetime(2027, 3, 15)
        assert s2.contexto.fechas_por_servicio[2] == datetime.datetime(2026, 11, 20)


# ---------------------------------------------------------------------------
# T-3T1: Three-tour loop
# ---------------------------------------------------------------------------


def _ctx_three_tours(**overrides: object) -> ContextoVenta:
    """ContextoVenta ready to enter FECHA_SALIDA with three tours selected."""
    defaults: dict[str, object] = {
        "destinos_numeros": [1, 2, 3],
        "destinos_nombres": ["Tour Playa Blanca", "Tour Isla", "City Tour"],
    }
    defaults.update(overrides)
    return ContextoVenta(**defaults)  # type: ignore[arg-type]


class TestThreeTourDateLoop:
    def test_first_date_stays_in_fecha_salida(self, fsm: FSMTiquetera) -> None:
        """First date entered stays in FECHA_SALIDA (2 tours still pending)."""
        ctx = _ctx_three_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "10/01/2027", ctx)
        assert s1.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_second_date_stays_in_fecha_salida(self, fsm: FSMTiquetera) -> None:
        """Second date entered stays in FECHA_SALIDA (1 tour still pending)."""
        ctx = _ctx_three_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "10/01/2027", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "15/02/2027", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_second_prompt_names_pending_tour(self, fsm: FSMTiquetera) -> None:
        """After first date, prompt names the SECOND pending tour."""
        ctx = _ctx_three_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "10/01/2027", ctx)
        assert "Tour Isla" in s1.mensaje

    def test_third_prompt_names_third_pending_tour(self, fsm: FSMTiquetera) -> None:
        """After second date, prompt names the THIRD pending tour."""
        ctx = _ctx_three_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "10/01/2027", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "15/02/2027", s1.contexto)
        assert "City Tour" in s2.mensaje

    def test_third_date_advances_to_pax_adultos(self, fsm: FSMTiquetera) -> None:
        """Third date entered advances to PAX_ADULTOS."""
        ctx = _ctx_three_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "10/01/2027", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "15/02/2027", s1.contexto)
        s3 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "05/12/2026", s2.contexto)
        assert s3.nuevo_estado == EstadoFSM.PAX_ADULTOS

    def test_all_three_keys_in_fechas_por_servicio(self, fsm: FSMTiquetera) -> None:
        """After all 3 dates, fechas_por_servicio has entries for tours 1, 2, and 3."""
        ctx = _ctx_three_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "10/01/2027", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "15/02/2027", s1.contexto)
        s3 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "05/12/2026", s2.contexto)
        fps = s3.contexto.fechas_por_servicio
        assert 1 in fps
        assert 2 in fps
        assert 3 in fps

    def test_fecha_salida_is_min_of_three(self, fsm: FSMTiquetera) -> None:
        """fecha_salida == min(all three per-tour dates)."""
        ctx = _ctx_three_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "10/01/2027", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "15/02/2027", s1.contexto)
        s3 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "05/12/2026", s2.contexto)
        # 05/12/2026 is the earliest
        assert s3.contexto.fecha_salida == datetime.datetime(2026, 12, 5)


# ---------------------------------------------------------------------------
# T-SD1: Same-date two-tour — both keys present, no short-circuit
# ---------------------------------------------------------------------------


class TestSameDateTwoTour:
    def test_same_date_both_keys_present(self, fsm: FSMTiquetera) -> None:
        """When both tours have the same date, fechas_por_servicio has BOTH keys."""
        ctx = _ctx_two_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", s1.contexto)
        fps = s2.contexto.fechas_por_servicio
        assert 1 in fps
        assert 2 in fps
        assert fps[1] == datetime.datetime(2026, 12, 25)
        assert fps[2] == datetime.datetime(2026, 12, 25)

    def test_same_date_fecha_salida_correct(self, fsm: FSMTiquetera) -> None:
        """When both tours share a date, fecha_salida == that shared date."""
        ctx = _ctx_two_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", s1.contexto)
        assert s2.contexto.fecha_salida == datetime.datetime(2026, 12, 25)

    def test_same_date_advances_to_pax_adultos(self, fsm: FSMTiquetera) -> None:
        """Same date for both tours still advances to PAX_ADULTOS."""
        ctx = _ctx_two_tours()
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.PAX_ADULTOS


# ---------------------------------------------------------------------------
# T-PH2: Photo full multi-tour map — auto-advance past FECHA_SALIDA
# ---------------------------------------------------------------------------


class TestPhotoMultiTourFullMap:
    def test_photo_advances_past_fecha_salida_when_fully_filled(
        self, fsm: FSMTiquetera
    ) -> None:
        """procesar_foto advances past FECHA_SALIDA when both per-tour dates are present."""
        dt1 = datetime.datetime(2026, 12, 20, 10, 0)
        dt2 = datetime.datetime(2026, 12, 22, 9, 0)
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            cliente_nombre="Juan",
            cliente_telefono="300",
            sin_hotel=True,
            fechas_por_servicio={1: dt1, 2: dt2},
            fecha_salida=min(dt1, dt2),
            adultos=0,  # stops at PAX_ADULTOS
        )
        salida = fsm.procesar_foto(EstadoFSM.CLIENTE_HABITACION, "101", ctx)
        # Must NOT be stuck at FECHA_SALIDA — advances to PAX_ADULTOS
        assert salida.nuevo_estado != EstadoFSM.FECHA_SALIDA
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS


# ---------------------------------------------------------------------------
# T-ED1: Edit Destinos — prune stale dates and re-capture missing ones (Slice 4)
# ---------------------------------------------------------------------------

# Catalog categories for the SERVICIOS_2TOURS fixture:
#   service 1 → "BARÚ"   (fam index 0 when families are sorted)
#   service 2 → "ISLAS"  (fam index 1)
#   service 3 → "ISLAS"  (fam index 1)
_CATEGORIA_POR_SERVICIO: dict[int, str] = {1: "BARÚ", 2: "ISLAS", 3: "ISLAS"}


def _indice_familia(fsm: FSMTiquetera, categoria: str) -> int:
    """Return the fam-index for *categoria* in the current FSM instance."""
    s = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ContextoVenta())
    assert s.opciones_estructuradas is not None
    for idx, (label, _) in enumerate(s.opciones_estructuradas):
        if label == categoria:
            return idx
    raise AssertionError(f"categoria {categoria!r} not found in picker")


def _add_tour_via_picker(
    fsm: FSMTiquetera, ctx: ContextoVenta, numero: int
) -> ContextoVenta:
    """Navigate FAMILIA → SERVICIO_EN_FAMILIA to add *numero* to the accumulator."""
    categoria = _CATEGORIA_POR_SERVICIO[numero]
    fam_idx = _indice_familia(fsm, categoria)
    # Pick the family
    s1 = fsm.procesar(EstadoFSM.FAMILIA, f"fam:{fam_idx}", ctx)
    # Pick the service
    s2 = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, f"srv:{numero}", s1.contexto)
    return s2.contexto


def _reach_familia_edit(fsm: FSMTiquetera, ctx: ContextoVenta) -> ContextoVenta:
    """Press EDITAR_SELECTOR 'Destinos' and return the resulting context (now at FAMILIA)."""
    s = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Destinos", ctx)
    assert s.nuevo_estado == EstadoFSM.FAMILIA
    return s.contexto


class TestEditarDestinosPruneAndRecapture:
    """Slice 4: confirm-in-edit on DESTINO prunes stale dates and routes to FECHA_SALIDA
    for any tour without a date, then returns to CONFIRMACION when all dates are filled.

    These tests use fsm_multi (multi_tour_habilitado=True) because they exercise the
    multi-tour accumulator edit flow (pick multiple tours via DESTINO, then confirm).
    """

    # ── T-ED1a: Partial replace [1,2]→[1,3]: key 2 pruned, route to FECHA_SALIDA for tour 3
    def test_partial_replace_prunes_stale_date(self, fsm_multi: FSMTiquetera) -> None:
        """After re-picking [1,3] from [1,2], key 2 must be pruned from fechas_por_servicio."""
        date1 = datetime.datetime(2026, 12, 20)
        date2 = datetime.datetime(2026, 12, 22)
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            adultos=1,
            ninos=0,
            fechas_por_servicio={1: date1, 2: date2},
            fecha_salida=date1,
        )
        # Edit Destinos → re-pick [1, 3] via proper FAMILIA → SERVICIO_EN_FAMILIA
        fam_ctx = _reach_familia_edit(fsm_multi, ctx)
        acc1 = _add_tour_via_picker(fsm_multi, fam_ctx, 1)
        acc2 = _add_tour_via_picker(fsm_multi, acc1, 3)
        confirm_msg = obtener_mensaje("opcion_confirmar_destinos")
        result = fsm_multi.procesar(EstadoFSM.DESTINO, confirm_msg, acc2)
        # Key 2 must be pruned; key 1 must survive
        assert 2 not in result.contexto.fechas_por_servicio
        assert 1 in result.contexto.fechas_por_servicio
        assert result.contexto.fechas_por_servicio[1] == date1

    def test_partial_replace_routes_to_fecha_salida_for_missing_tour(
        self, fsm_multi: FSMTiquetera
    ) -> None:
        """After re-picking [1,3], FSM must route to FECHA_SALIDA (tour 3 has no date)."""
        date1 = datetime.datetime(2026, 12, 20)
        date2 = datetime.datetime(2026, 12, 22)
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            adultos=1,
            ninos=0,
            fechas_por_servicio={1: date1, 2: date2},
            fecha_salida=date1,
        )
        fam_ctx = _reach_familia_edit(fsm_multi, ctx)
        acc1 = _add_tour_via_picker(fsm_multi, fam_ctx, 1)
        acc2 = _add_tour_via_picker(fsm_multi, acc1, 3)
        confirm_msg = obtener_mensaje("opcion_confirmar_destinos")
        result = fsm_multi.procesar(EstadoFSM.DESTINO, confirm_msg, acc2)
        assert result.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_partial_replace_prompt_names_tour_3(self, fsm_multi: FSMTiquetera) -> None:
        """The FECHA_SALIDA prompt must name 'City Tour' (tour 3, the missing one).

        The state must be FECHA_SALIDA, not CONFIRMACION — otherwise the mensaje
        assertion would pass trivially via the resumen which also names the tours.
        """
        date1 = datetime.datetime(2026, 12, 20)
        date2 = datetime.datetime(2026, 12, 22)
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            adultos=1,
            ninos=0,
            fechas_por_servicio={1: date1, 2: date2},
            fecha_salida=date1,
        )
        fam_ctx = _reach_familia_edit(fsm_multi, ctx)
        acc1 = _add_tour_via_picker(fsm_multi, fam_ctx, 1)
        acc2 = _add_tour_via_picker(fsm_multi, acc1, 3)
        confirm_msg = obtener_mensaje("opcion_confirmar_destinos")
        result = fsm_multi.procesar(EstadoFSM.DESTINO, confirm_msg, acc2)
        # Must be at FECHA_SALIDA (not CONFIRMACION, which also names tours in the resumen)
        assert result.nuevo_estado == EstadoFSM.FECHA_SALIDA
        # "City Tour" is the name for service 3 — the per-tour date prompt names it
        assert "City Tour" in result.mensaje

    def test_partial_replace_capture_tour3_then_back_to_confirmacion(
        self, fsm_multi: FSMTiquetera
    ) -> None:
        """Feed tour 3's date → FSM returns to CONFIRMACION; fecha_salida == min(date1, date3)."""
        date1 = datetime.datetime(2026, 12, 20)
        date2 = datetime.datetime(2026, 12, 22)
        date3 = datetime.datetime(2026, 12, 18)  # earlier than date1
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            adultos=1,
            ninos=0,
            fechas_por_servicio={1: date1, 2: date2},
            fecha_salida=date1,
        )
        fam_ctx = _reach_familia_edit(fsm_multi, ctx)
        acc1 = _add_tour_via_picker(fsm_multi, fam_ctx, 1)
        acc2 = _add_tour_via_picker(fsm_multi, acc1, 3)
        confirm_msg = obtener_mensaje("opcion_confirmar_destinos")
        at_fecha = fsm_multi.procesar(EstadoFSM.DESTINO, confirm_msg, acc2)
        assert at_fecha.nuevo_estado == EstadoFSM.FECHA_SALIDA
        # Now feed tour 3's date
        final = fsm_multi.procesar(EstadoFSM.FECHA_SALIDA, "18/12/2026", at_fecha.contexto)
        assert final.nuevo_estado == EstadoFSM.CONFIRMACION
        assert final.contexto.fecha_salida == min(date1, date3)
        assert final.contexto.fechas_por_servicio[3] == date3

    # ── T-ED1b: Same set re-picked [1,2]→[1,2]: no recapture, dates preserved
    def test_same_set_repicked_goes_to_confirmacion(self, fsm_multi: FSMTiquetera) -> None:
        """Re-picking the same tours [1,2] that already have dates → CONFIRMACION, no recapture."""
        date1 = datetime.datetime(2026, 12, 20)
        date2 = datetime.datetime(2026, 12, 22)
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            adultos=1,
            ninos=0,
            fechas_por_servicio={1: date1, 2: date2},
            fecha_salida=date1,
        )
        fam_ctx = _reach_familia_edit(fsm_multi, ctx)
        acc1 = _add_tour_via_picker(fsm_multi, fam_ctx, 1)
        acc2 = _add_tour_via_picker(fsm_multi, acc1, 2)
        confirm_msg = obtener_mensaje("opcion_confirmar_destinos")
        result = fsm_multi.procesar(EstadoFSM.DESTINO, confirm_msg, acc2)
        assert result.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_same_set_repicked_preserves_dates(self, fsm_multi: FSMTiquetera) -> None:
        """Re-picking [1,2] with existing dates → both dates preserved, state == CONFIRMACION."""
        date1 = datetime.datetime(2026, 12, 20)
        date2 = datetime.datetime(2026, 12, 22)
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            adultos=1,
            ninos=0,
            fechas_por_servicio={1: date1, 2: date2},
            fecha_salida=date1,
        )
        fam_ctx = _reach_familia_edit(fsm_multi, ctx)
        acc1 = _add_tour_via_picker(fsm_multi, fam_ctx, 1)
        acc2 = _add_tour_via_picker(fsm_multi, acc1, 2)
        confirm_msg = obtener_mensaje("opcion_confirmar_destinos")
        result = fsm_multi.procesar(EstadoFSM.DESTINO, confirm_msg, acc2)
        assert result.nuevo_estado == EstadoFSM.CONFIRMACION
        assert result.contexto.fechas_por_servicio == {1: date1, 2: date2}
        assert result.contexto.fecha_salida == date1

    # ── T-ED1c: Removal [1,2]→[1]: dict pruned to {1}, fecha_salida==date1
    def test_removal_prunes_dict_to_kept_tour(self, fsm_multi: FSMTiquetera) -> None:
        """Re-picking only [1] from [1,2] → fechas_por_servicio == {1: date1}."""
        date1 = datetime.datetime(2026, 12, 20)
        date2 = datetime.datetime(2026, 12, 22)
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            adultos=1,
            ninos=0,
            fechas_por_servicio={1: date1, 2: date2},
            fecha_salida=date1,
        )
        fam_ctx = _reach_familia_edit(fsm_multi, ctx)
        acc1 = _add_tour_via_picker(fsm_multi, fam_ctx, 1)
        confirm_msg = obtener_mensaje("opcion_confirmar_destinos")
        result = fsm_multi.procesar(EstadoFSM.DESTINO, confirm_msg, acc1)
        assert result.nuevo_estado == EstadoFSM.CONFIRMACION
        assert result.contexto.fechas_por_servicio == {1: date1}
        assert result.contexto.fecha_salida == date1

    # ── T-ED1d: Full replace [1,2]→[3]: dict empty after prune → FECHA_SALIDA
    def test_full_replace_empty_dict_routes_to_fecha_salida(
        self, fsm_multi: FSMTiquetera
    ) -> None:
        """Re-picking [3] from [1,2] (none kept) → fechas pruned to {}, route to FECHA_SALIDA."""
        date1 = datetime.datetime(2026, 12, 20)
        date2 = datetime.datetime(2026, 12, 22)
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            adultos=1,
            ninos=0,
            fechas_por_servicio={1: date1, 2: date2},
            fecha_salida=date1,
        )
        fam_ctx = _reach_familia_edit(fsm_multi, ctx)
        acc1 = _add_tour_via_picker(fsm_multi, fam_ctx, 3)
        confirm_msg = obtener_mensaje("opcion_confirmar_destinos")
        result = fsm_multi.procesar(EstadoFSM.DESTINO, confirm_msg, acc1)
        assert result.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert result.contexto.fechas_por_servicio == {}

    def test_full_replace_capture_date_then_confirmacion(
        self, fsm_multi: FSMTiquetera
    ) -> None:
        """After full replace to [3], capture its date → CONFIRMACION, fecha_salida == date3."""
        date1 = datetime.datetime(2026, 12, 20)
        date2 = datetime.datetime(2026, 12, 22)
        date3 = datetime.datetime(2026, 12, 15)
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            adultos=1,
            ninos=0,
            fechas_por_servicio={1: date1, 2: date2},
            fecha_salida=date1,
        )
        fam_ctx = _reach_familia_edit(fsm_multi, ctx)
        acc1 = _add_tour_via_picker(fsm_multi, fam_ctx, 3)
        confirm_msg = obtener_mensaje("opcion_confirmar_destinos")
        at_fecha = fsm_multi.procesar(EstadoFSM.DESTINO, confirm_msg, acc1)
        assert at_fecha.nuevo_estado == EstadoFSM.FECHA_SALIDA
        final = fsm_multi.procesar(EstadoFSM.FECHA_SALIDA, "15/12/2026", at_fecha.contexto)
        assert final.nuevo_estado == EstadoFSM.CONFIRMACION
        assert final.contexto.fecha_salida == date3
        assert final.contexto.fechas_por_servicio == {3: date3}

    # ── T-ED1e: Neto recomputed after edit
    def test_neto_recomputed_after_destinos_edit(self, fsm_multi: FSMTiquetera) -> None:
        """ctx.neto must reflect the NEW tour set after Destinos edit, not the stale value."""
        date1 = datetime.datetime(2026, 12, 20)
        date2 = datetime.datetime(2026, 12, 22)
        # Start: [1, 2] both priced, adultos=1 → neto = 100000 + 150000 = 250000
        stale_neto = Decimal("250000")
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla"],
            adultos=1,
            ninos=0,
            neto=stale_neto,
            fechas_por_servicio={1: date1, 2: date2},
            fecha_salida=date1,
        )
        # Edit Destinos → keep only tour 1 (neto should become 100000)
        fam_ctx = _reach_familia_edit(fsm_multi, ctx)
        acc1 = _add_tour_via_picker(fsm_multi, fam_ctx, 1)
        confirm_msg = obtener_mensaje("opcion_confirmar_destinos")
        result = fsm_multi.procesar(EstadoFSM.DESTINO, confirm_msg, acc1)
        # Should be at CONFIRMACION (tour 1 already has a date) with updated neto
        assert result.nuevo_estado == EstadoFSM.CONFIRMACION
        assert result.contexto.neto == Decimal("100000")
