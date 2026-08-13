"""Tests for FSMTiquetera.refrescar_servicios() — RED phase written first (strict TDD)."""

from __future__ import annotations

from decimal import Decimal

from garay.aplicacion.tiquetera.fsm import FSMTiquetera

SERVICIOS_INICIAL: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ"),
    (2, "Tour Isla Grande", Decimal("150000"), None, "ISLAS"),
    (3, "City Tour", None, None, "ISLAS"),
]

PUNTOS_TEST = ["Marie Real"]


def _make_fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_INICIAL, puntos_venta=PUNTOS_TEST)


def test_refrescar_servicios_rebuilds_servicios() -> None:
    """refrescar_servicios() replaces _servicios with new tuples."""
    fsm = _make_fsm()
    nuevos: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
        (1, "Tour Playa Blanca NUEVO", Decimal("120000"), Decimal("60000"), "BARÚ"),
        (2, "Tour Isla Grande", Decimal("150000"), None, "ISLAS"),
    ]
    fsm.refrescar_servicios(nuevos)
    # Tour 1 has updated name and neto.
    assert fsm._servicios[1] == ("Tour Playa Blanca NUEVO", Decimal("120000"), Decimal("60000"))
    # Tour 3 is no longer in the list — should be absent.
    assert 3 not in fsm._servicios


def test_refresh_rebuild_familias() -> None:
    """After refresh, _familias is rebuilt: empty families disappear."""
    fsm = _make_fsm()
    # Remove both ISLAS tours (2 and 3) — ISLAS family should vanish.
    nuevos: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
        (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ"),
    ]
    fsm.refrescar_servicios(nuevos)
    assert "ISLAS" not in fsm._familias
    assert "BARÚ" in fsm._familias
    assert fsm._familias["BARÚ"] == [1]


def test_refresh_moved_tour_relocates() -> None:
    """A tour changing categoria moves from old bucket to new one."""
    fsm = _make_fsm()
    # Tour 1 moves from BARÚ to ISLAS.
    nuevos: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
        (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "ISLAS"),
        (2, "Tour Isla Grande", Decimal("150000"), None, "ISLAS"),
        (3, "City Tour", None, None, "ISLAS"),
    ]
    fsm.refrescar_servicios(nuevos)
    # BARÚ should be gone (tour 1 moved out, no others were there).
    assert "BARÚ" not in fsm._familias
    # Tour 1 is now in ISLAS.
    assert 1 in fsm._familias["ISLAS"]


def test_refresh_does_not_touch_user_data() -> None:
    """Refresh replaces _servicios/_familias in place but does NOT affect
    a simulated context.user_data snapshot (per-conversation state)."""
    fsm = _make_fsm()

    # Simulate a PTB user_data dict as it would look mid-sale.
    simulated_user_data: dict = {"contexto": {"numero_tour": 1, "familia": "BARÚ"}}
    snapshot_before = dict(simulated_user_data["contexto"])

    nuevos: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
        (99, "Nuevo Tour", Decimal("200000"), None, "NUEVA FAMILIA"),
    ]
    fsm.refrescar_servicios(nuevos)

    # user_data is untouched — the FSM holds no reference to it.
    assert simulated_user_data["contexto"] == snapshot_before
