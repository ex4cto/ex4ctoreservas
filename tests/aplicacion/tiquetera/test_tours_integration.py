"""Integration test: edit tour → guardar → refrescar → new sale sees the change."""

from __future__ import annotations

import uuid
from decimal import Decimal

from garay.aplicacion.tiquetera.fsm import FSMTiquetera
from garay.dominio.servicios.entidades import Servicio


def _make_fsm(servicios: list[Servicio]) -> FSMTiquetera:
    tuples = [
        (s.numero, s.nombre, s.precio_neto_adulto, s.precio_neto_nino, s.categoria)
        for s in servicios
    ]
    return FSMTiquetera(servicios=tuples, puntos_venta=["Marie Real"])


class TestEditSaveRefreshVisibleToNewSale:
    def test_edit_save_refresh_visible_to_new_sale(self) -> None:
        """Edit tour name, refresh FSM, new sale flow sees the updated name."""
        s1 = Servicio(
            id=uuid.uuid4(),
            numero=1,
            nombre="City Tour Original",
            categoria="Cartagena",
            activo=True,
            precio_neto_adulto=Decimal("30000"),
        )
        fsm = _make_fsm([s1])

        # _servicios[numero] = (nombre, neto_adulto, neto_nino)
        assert fsm._servicios[1][0] == "City Tour Original"

        # Simulate edit: rename the tour
        s1.nombre = "City Tour Actualizado"

        # Refresh FSM with updated data
        tuples = [
            (s1.numero, s1.nombre, s1.precio_neto_adulto, s1.precio_neto_nino, s1.categoria)
        ]
        fsm.refrescar_servicios(tuples)

        # New sale starts → FSM returns updated name
        assert fsm._servicios[1][0] == "City Tour Actualizado"


class TestDesactivarTourOcultoEnVentas:
    def test_desactivar_tour_refresco_usa_listar_activos(self) -> None:
        """After deactivating a tour, refreshing with listar_activos result removes it."""
        s1 = Servicio(
            id=uuid.uuid4(),
            numero=1,
            nombre="Active Tour",
            categoria="Cartagena",
            activo=True,
            precio_neto_adulto=Decimal("30000"),
        )
        s2 = Servicio(
            id=uuid.uuid4(),
            numero=2,
            nombre="To Delete",
            categoria="Cartagena",
            activo=True,
            precio_neto_adulto=Decimal("20000"),
        )
        fsm = _make_fsm([s1, s2])
        assert 1 in fsm._servicios
        assert 2 in fsm._servicios

        # Soft-delete s2
        s2.activo = False

        # Refresh with only active tours (listar_activos() result)
        activos = [s for s in [s1, s2] if s.activo]
        tuples = [
            (s.numero, s.nombre, s.precio_neto_adulto, s.precio_neto_nino, s.categoria)
            for s in activos
        ]
        fsm.refrescar_servicios(tuples)

        # s2 must be gone from FSM catalog
        assert 2 not in fsm._servicios
        # s1 must still be there
        assert 1 in fsm._servicios
