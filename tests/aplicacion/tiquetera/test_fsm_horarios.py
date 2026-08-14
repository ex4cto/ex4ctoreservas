"""Tests for FSM catalog 6-tuple extension and self._horarios — Phase 4, WU-1.

Follows strict TDD: RED tests are written first, then GREEN implementation.
PR A scope: catalog plumbing only (no HORARIO_SALIDA state, no call-sites).
"""

from __future__ import annotations

from decimal import Decimal

from garay.aplicacion.tiquetera.fsm import FSMTiquetera
from tests.aplicacion.tiquetera.conftest import catalogo_fsm

# ---------------------------------------------------------------------------
# Phase 2.1 RED — _build_catalog must populate self._horarios (new dict)
# ---------------------------------------------------------------------------


class TestHorariosDict:
    """self._horarios is a dict[int, list[str]] populated from the 6th tuple element."""

    def test_horarios_dict_populated(self) -> None:
        """FSM built with non-empty horarios stores them in _horarios keyed by numero."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00", "09:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        assert fsm._horarios[1] == ["07:00", "09:00"]

    def test_horarios_empty_default(self) -> None:
        """FSM built with empty horarios stores [] for that tour."""
        servicios = catalogo_fsm()
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        assert fsm._horarios[1] == []

    def test_horarios_multiple_tours(self) -> None:
        """When catalog has multiple tours, _horarios has an entry for each."""
        servicios = catalogo_fsm(
            {"numero": 1, "horarios": ["07:00"]},
            {"numero": 2, "nombre": "Tour B", "horarios": []},
        )
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        assert fsm._horarios[1] == ["07:00"]
        assert fsm._horarios[2] == []

    def test_servicios_internal_layout_unchanged(self) -> None:
        """Internal _servicios keeps 3-tuple layout; adding _horarios must not change it."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["08:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        # _servicios[1] must be exactly (nombre, neto_a, neto_n) — the 3-tuple
        nombre, neto_a, neto_n = fsm._servicios[1]
        assert nombre == "Tour"
        assert neto_a == Decimal("50")
        assert neto_n == Decimal("25")


class TestRefrescarServicios6Tuples:
    """refrescar_servicios must accept 6-tuples and update _horarios."""

    def test_refrescar_servicios_accepts_6_tuples(self) -> None:
        """After refrescar_servicios with 6-tuples, _horarios is updated."""
        servicios = catalogo_fsm()
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        assert fsm._horarios[1] == []

        nuevos = catalogo_fsm({"numero": 1, "horarios": ["10:00", "14:00"]})
        fsm.refrescar_servicios(nuevos)
        assert fsm._horarios[1] == ["10:00", "14:00"]

    def test_refrescar_servicios_clears_old_horarios(self) -> None:
        """After refresh, tours no longer present are removed from _horarios."""
        servicios = catalogo_fsm(
            {"numero": 1, "horarios": ["07:00"]},
            {"numero": 2, "nombre": "Tour B", "horarios": ["09:00"]},
        )
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        assert 2 in fsm._horarios

        nuevos = catalogo_fsm({"numero": 1, "horarios": ["08:00"]})
        fsm.refrescar_servicios(nuevos)
        assert fsm._horarios[1] == ["08:00"]
        assert 2 not in fsm._horarios
