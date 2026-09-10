"""FSM: skip the children prompt when no selected tour admits children.

Item A, slice A2. The catalog carries a per-tour permite_ninos flag; when NONE of
the selected tours admits children, PAX_ADULTOS must skip PAX_NINOS, set ninos=0,
and advance to the next state (MONTO_VALOR, or CONFIRMACION in edit mode).
"""

from __future__ import annotations

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta
from tests.aplicacion.tiquetera.conftest import catalogo_fsm

_PDV = ["Marie Real"]


def _fsm(permite: dict[int, bool] | None) -> FSMTiquetera:
    return FSMTiquetera(
        servicios=catalogo_fsm({"numero": 1}, {"numero": 2}),
        puntos_venta=_PDV,
        permite_ninos=permite,
    )


def test_salta_pregunta_ninos_si_el_unico_tour_no_permite() -> None:
    fsm = _fsm({1: False})
    ctx = ContextoVenta(destinos_numeros=[1])
    salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "2", ctx)
    assert salida.nuevo_estado == EstadoFSM.MONTO_VALOR
    assert salida.contexto.ninos == 0


def test_pregunta_ninos_si_el_tour_permite() -> None:
    fsm = _fsm({1: True})
    ctx = ContextoVenta(destinos_numeros=[1])
    salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "2", ctx)
    assert salida.nuevo_estado == EstadoFSM.PAX_NINOS


def test_pregunta_ninos_por_defecto_sin_mapa() -> None:
    fsm = _fsm(None)
    ctx = ContextoVenta(destinos_numeros=[1])
    salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "2", ctx)
    assert salida.nuevo_estado == EstadoFSM.PAX_NINOS


def test_pregunta_ninos_si_al_menos_uno_permite() -> None:
    fsm = _fsm({1: False, 2: True})
    ctx = ContextoVenta(destinos_numeros=[1, 2])
    salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "2", ctx)
    assert salida.nuevo_estado == EstadoFSM.PAX_NINOS


def test_salta_si_ningun_tour_del_grupo_permite() -> None:
    fsm = _fsm({1: False, 2: False})
    ctx = ContextoVenta(destinos_numeros=[1, 2])
    salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "2", ctx)
    assert salida.nuevo_estado == EstadoFSM.MONTO_VALOR
    assert salida.contexto.ninos == 0


def test_salto_en_modo_edicion_va_a_confirmacion() -> None:
    fsm = _fsm({1: False})
    ctx = ContextoVenta(destinos_numeros=[1], modo_edicion=True)
    salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "2", ctx)
    assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
    assert salida.contexto.ninos == 0


def test_refrescar_servicios_actualiza_permite_ninos() -> None:
    fsm = _fsm(None)  # arranca permitiendo niños
    fsm.refrescar_servicios(catalogo_fsm({"numero": 1}), {1: False})
    ctx = ContextoVenta(destinos_numeros=[1])
    salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "2", ctx)
    assert salida.nuevo_estado == EstadoFSM.MONTO_VALOR
    assert salida.contexto.ninos == 0
