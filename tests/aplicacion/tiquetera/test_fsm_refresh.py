"""Tests for FSMTiquetera.refrescar_servicios() and related integration scenarios.

All tests in this file follow strict TDD (RED first, then GREEN).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from garay.aplicacion.tiquetera.fsm import FSMTiquetera
from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.persistencia import modelos  # noqa: F401
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.repositorios.servicios import SQLAServicioRepository

SERVICIOS_INICIAL: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ", []),
    (2, "Tour Isla Grande", Decimal("150000"), None, "ISLAS", []),
    (3, "City Tour", None, None, "ISLAS", []),
]

PUNTOS_TEST = ["Marie Real"]


def _make_fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_INICIAL, puntos_venta=PUNTOS_TEST)


def test_refrescar_servicios_rebuilds_servicios() -> None:
    """refrescar_servicios() replaces _servicios with new tuples."""
    fsm = _make_fsm()
    nuevos: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
        (1, "Tour Playa Blanca NUEVO", Decimal("120000"), Decimal("60000"), "BARÚ", []),
        (2, "Tour Isla Grande", Decimal("150000"), None, "ISLAS", []),
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
    nuevos: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
        (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ", []),
    ]
    fsm.refrescar_servicios(nuevos)
    assert "ISLAS" not in fsm._familias
    assert "BARÚ" in fsm._familias
    assert fsm._familias["BARÚ"] == [1]


def test_refresh_moved_tour_relocates() -> None:
    """A tour changing categoria moves from old bucket to new one."""
    fsm = _make_fsm()
    # Tour 1 moves from BARÚ to ISLAS.
    nuevos: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
        (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "ISLAS", []),
        (2, "Tour Isla Grande", Decimal("150000"), None, "ISLAS", []),
        (3, "City Tour", None, None, "ISLAS", []),
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
    simulated_user_data: dict[str, dict[str, object]] = {
        "contexto": {"numero_tour": 1, "familia": "BARÚ"}
    }
    snapshot_before = dict(simulated_user_data["contexto"])

    nuevos: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
        (99, "Nuevo Tour", Decimal("200000"), None, "NUEVA FAMILIA", []),
    ]
    fsm.refrescar_servicios(nuevos)

    # user_data is untouched — the FSM holds no reference to it.
    assert simulated_user_data["contexto"] == snapshot_before


# ── Phase 8.2 — integration: deactivated tour hidden from listar_activos ──────


@pytest.fixture()
def sf_mem() -> sessionmaker[Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_desactivar_tour_oculto_en_listar_activos(sf_mem: sessionmaker[Session]) -> None:
    """After setting activo=False and saving, listar_activos() must NOT return
    the tour; listar() must still return it (soft-delete semantics)."""
    repo = SQLAServicioRepository(sf_mem)
    tour = Servicio(
        id=uuid.uuid4(),
        numero=42,
        nombre="Tour a Desactivar",
        activo=True,
        precio_neto_adulto=Decimal("80000"),
        precio_neto_nino=None,
        categoria="PRUEBA",
    )
    repo.guardar(tour)

    # Confirm it's visible before deactivation.
    assert any(s.id == tour.id for s in repo.listar_activos())

    # Soft-delete: set activo=False and save.
    import dataclasses

    inactivo = dataclasses.replace(tour, activo=False)
    repo.guardar(inactivo)

    # Must be absent from listar_activos().
    assert all(s.id != tour.id for s in repo.listar_activos())
    # Must still be present in listar() (data not destroyed).
    assert any(s.id == tour.id for s in repo.listar())


# ── freelancer roster refresh ────────────────────────────────────────────────


def _fsm_con_freelancers(
    freelancers: list[tuple[uuid.UUID, str, bool]],
) -> FSMTiquetera:
    return FSMTiquetera(
        servicios=SERVICIOS_INICIAL,
        puntos_venta=PUNTOS_TEST,
        freelancers=freelancers,
    )


def test_refrescar_freelancers_agrega_nuevo() -> None:
    """A newly added freelancer appears in the sale picker after refresh."""
    id_a, id_b = uuid.uuid4(), uuid.uuid4()
    fsm = _fsm_con_freelancers([(id_a, "Ana", True)])

    fsm.refrescar_freelancers([(id_a, "Ana", True), (id_b, "Bruno", True)])

    labels = [lbl for lbl, _ in fsm._opciones_freelancers(solo_activos=True)]
    assert labels == ["Ana", "Bruno"]


def test_refrescar_freelancers_elimina_removido() -> None:
    """A freelancer no longer in the roster disappears from every picker."""
    id_a, id_b = uuid.uuid4(), uuid.uuid4()
    fsm = _fsm_con_freelancers([(id_a, "Ana", True), (id_b, "Bruno", True)])

    fsm.refrescar_freelancers([(id_a, "Ana", True)])

    valores = [val for _, val in fsm._opciones_freelancers(solo_activos=False)]
    assert valores == [f"fl:{id_a}"]


def test_refrescar_freelancers_renombra() -> None:
    """Editing a freelancer's name is reflected after refresh."""
    id_a = uuid.uuid4()
    fsm = _fsm_con_freelancers([(id_a, "Ana", True)])

    fsm.refrescar_freelancers([(id_a, "Ana Maria", True)])

    labels = [lbl for lbl, _ in fsm._opciones_freelancers(solo_activos=True)]
    assert labels == ["Ana Maria"]


def test_refrescar_freelancers_conserva_inactivos_para_edicion() -> None:
    """Refresh MUST keep inactive freelancers: hidden from the sale picker but
    still shown (with [inactivo]) in the participant-edit picker. This is why the
    refresh mirrors listar_todos(), NOT listar_activos()."""
    id_a = uuid.uuid4()
    fsm = _fsm_con_freelancers([(id_a, "Ana", True)])

    fsm.refrescar_freelancers([(id_a, "Ana", False)])

    # Hidden from the sale picker (solo_activos=True)...
    assert fsm._opciones_freelancers(solo_activos=True) == []
    # ...but present in the edit picker (solo_activos=False) with the suffix.
    assert fsm._opciones_freelancers(solo_activos=False) == [
        ("Ana [inactivo]", f"fl:{id_a}")
    ]
