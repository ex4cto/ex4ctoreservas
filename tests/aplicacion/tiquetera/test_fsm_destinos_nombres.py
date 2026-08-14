"""Tests for Bug Fix: _handle_servicio_en_familia must populate destinos_nombres.

ROOT CAUSE: The manual flow appended to destinos_numeros but never appended
to destinos_nombres. Only the photo flow (via extractor_reserva) populated it.

Scenarios:
  - Normal registration (one-tour mode): after picking a tour, destinos_nombres
    has the tour's name and is index-aligned with destinos_numeros.
  - Duplicate guard: re-picking the same tour does not double-add the name.
  - del:{numero} accumulator removal also removes the aligned name entry.
  - tour_adicional path: nombre also populated when skipping to FECHA_SALIDA.
  - Edit mode path: nombre populated when editing Destinos.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ", []),
    (2, "Tour Isla Bonita", Decimal("150000"), None, "ISLAS", []),
    (3, "Tour City Walk", Decimal("80000"), Decimal("40000"), "CIUDAD", []),
]
PUNTOS_TEST: list[str] = ["Marie Real"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


@pytest.fixture()
def fsm_multi() -> FSMTiquetera:
    return FSMTiquetera(
        servicios=SERVICIOS_TEST,
        puntos_venta=PUNTOS_TEST,
        multi_tour_habilitado=True,
    )


# ---------------------------------------------------------------------------
# Task 1a: Normal one-tour registration path
# ---------------------------------------------------------------------------


class TestDestinosNombresNormalPath:
    """After picking a tour, destinos_nombres must contain the tour name."""

    def test_picking_tour_populates_destinos_nombres(self, fsm: FSMTiquetera) -> None:
        """destinos_nombres must be ['Tour Playa Blanca'] after picking srv:1."""
        ctx = ContextoVenta(familia_seleccionada="BARÚ")
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.contexto.destinos_nombres == ["Tour Playa Blanca"]

    def test_picking_different_tour_populates_correct_name(
        self, fsm: FSMTiquetera
    ) -> None:
        """Triangulation: picking srv:2 gives 'Tour Isla Bonita'."""
        ctx = ContextoVenta(familia_seleccionada="ISLAS")
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:2", ctx)
        assert salida.contexto.destinos_nombres == ["Tour Isla Bonita"]

    def test_destinos_numeros_and_nombres_index_aligned(
        self, fsm: FSMTiquetera
    ) -> None:
        """destinos_numeros[0] and destinos_nombres[0] refer to the same tour."""
        ctx = ContextoVenta(familia_seleccionada="BARÚ")
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert len(salida.contexto.destinos_numeros) == len(
            salida.contexto.destinos_nombres
        )
        assert salida.contexto.destinos_numeros[0] == 1
        assert salida.contexto.destinos_nombres[0] == "Tour Playa Blanca"

    def test_duplicate_pick_does_not_double_add_name(
        self, fsm: FSMTiquetera
    ) -> None:
        """If numero already in destinos_numeros, name must not be added again."""
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            destinos_numeros=[1],
            destinos_nombres=["Tour Playa Blanca"],
        )
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.contexto.destinos_numeros.count(1) == 1
        assert salida.contexto.destinos_nombres.count("Tour Playa Blanca") == 1


# ---------------------------------------------------------------------------
# Task 1b: Accumulator removal keeps lists in sync (del:{numero} path)
# ---------------------------------------------------------------------------


class TestDelRemovalKeepsSync:
    """del:{numero} in DESTINO handler must remove the aligned name too."""

    def test_del_removes_name_from_destinos_nombres(
        self, fsm_multi: FSMTiquetera
    ) -> None:
        """After del:1, destinos_nombres must no longer contain 'Tour Playa Blanca'."""
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla Bonita"],
        )
        salida = fsm_multi.procesar(EstadoFSM.DESTINO, "del:1", ctx)
        assert "Tour Playa Blanca" not in salida.contexto.destinos_nombres
        assert salida.contexto.destinos_nombres == ["Tour Isla Bonita"]

    def test_del_keeps_remaining_name_aligned(
        self, fsm_multi: FSMTiquetera
    ) -> None:
        """After del:1, destinos_numeros=[2] aligns with destinos_nombres=['Tour Isla Bonita']."""
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Tour Playa Blanca", "Tour Isla Bonita"],
        )
        salida = fsm_multi.procesar(EstadoFSM.DESTINO, "del:1", ctx)
        assert salida.contexto.destinos_numeros == [2]
        assert salida.contexto.destinos_nombres == ["Tour Isla Bonita"]

    def test_del_last_item_empties_names(self, fsm_multi: FSMTiquetera) -> None:
        """del: last item → destinos_nombres is also empty (routes back to FAMILIA)."""
        ctx = ContextoVenta(
            destinos_numeros=[1],
            destinos_nombres=["Tour Playa Blanca"],
        )
        salida = fsm_multi.procesar(EstadoFSM.DESTINO, "del:1", ctx)
        assert salida.contexto.destinos_nombres == []
        assert salida.contexto.destinos_numeros == []


# ---------------------------------------------------------------------------
# Task 1c: tour_adicional path also populates destinos_nombres
# ---------------------------------------------------------------------------


class TestDestinosNombresTourAdicional:
    """When tour_adicional=True, picking a tour still populates destinos_nombres."""

    def test_tour_adicional_populates_nombres(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            cliente_nombre="Juan Perez",
            tour_adicional=True,
        )
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.contexto.destinos_nombres == ["Tour Playa Blanca"]


# ---------------------------------------------------------------------------
# Task 1d: edit mode path also populates destinos_nombres
# ---------------------------------------------------------------------------


class TestDestinosNombresModoEdicion:
    """In modo_edicion, picking a tour must also populate destinos_nombres."""

    def test_edit_mode_populates_nombre(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(
            familia_seleccionada="BARÚ",
            destinos_numeros=[],
            adultos=2,
            ninos=0,
            modo_edicion=True,
        )
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.contexto.destinos_nombres == ["Tour Playa Blanca"]
