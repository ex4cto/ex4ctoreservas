"""TDD tests for bug 1B: Playa Linda price + named-tour message when no price.

RED phase: these tests MUST fail before the implementation is in place.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta

# ── Test catalog ──────────────────────────────────────────────────────────────
# Tour 10: has price → auto-calculates
# Tour 20: priceless (Cocotera stand-in) → triggers MONTO_NETO
# Tour 30: priceless second tour → both names appear
# Tour 40: Playa Linda-like, with price 55000 per adult → auto-calculates
SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (10, "Tour Con Precio", Decimal("100000"), Decimal("50000"), "BARÚ", []),
    (20, "COCOTERA (CLASSIC)", None, None, "ISLAS", []),
    (30, "CENA SIBARITA", None, None, "ISLAS", []),
    (40, "PLAYA LINDA", Decimal("55000"), None, "TIERRA BOMBA", []),
]
PUNTOS_TEST: list[str] = ["Marie Real"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests for _tours_sin_precio helper
# ══════════════════════════════════════════════════════════════════════════════


class TestToursSinPrecio:
    """_tours_sin_precio must return names of selected tours with neto_adulto=None."""

    def test_returns_name_when_tour_has_no_neto_adulto(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[20])
        result = fsm._tours_sin_precio(ctx)
        assert result == ["COCOTERA (CLASSIC)"]

    def test_returns_empty_when_all_tours_have_price(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[10])
        result = fsm._tours_sin_precio(ctx)
        assert result == []

    def test_returns_multiple_names_when_multiple_tours_lack_price(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = ContextoVenta(destinos_numeros=[20, 30])
        result = fsm._tours_sin_precio(ctx)
        assert result == ["COCOTERA (CLASSIC)", "CENA SIBARITA"]

    def test_mixed_selection_returns_only_priceless_names(self, fsm: FSMTiquetera) -> None:
        # Tour 10 has price, tour 20 does not → only tour 20's name returned
        ctx = ContextoVenta(destinos_numeros=[10, 20])
        result = fsm._tours_sin_precio(ctx)
        assert result == ["COCOTERA (CLASSIC)"]

    def test_playa_linda_with_price_not_in_result(self, fsm: FSMTiquetera) -> None:
        # Tour 40 (PLAYA LINDA) has neto_adulto set → must NOT appear
        ctx = ContextoVenta(destinos_numeros=[40])
        result = fsm._tours_sin_precio(ctx)
        assert result == []


# ══════════════════════════════════════════════════════════════════════════════
# FSM integration: message names the priceless tour(s)
# ══════════════════════════════════════════════════════════════════════════════


class TestMensajeSinPrecioNombraTour:
    """When _calcular_neto returns None, the MONTO_NETO message must name the tour(s)."""

    def test_mensaje_contiene_nombre_del_tour_sin_precio(self, fsm: FSMTiquetera) -> None:
        # Tour 20 has no price → routes to MONTO_NETO with its name in the message
        ctx = ContextoVenta(
            destinos_numeros=[20],
            adultos=2,
            ninos=0,
            valor=Decimal("200000"),
        )
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.MONTO_NETO
        assert "COCOTERA (CLASSIC)" in salida.mensaje

    def test_mensaje_contiene_ambos_tours_sin_precio(self, fsm: FSMTiquetera) -> None:
        # Two priceless tours → both names in message
        ctx = ContextoVenta(
            destinos_numeros=[20, 30],
            adultos=1,
            ninos=0,
            valor=Decimal("300000"),
        )
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.MONTO_NETO
        assert "COCOTERA (CLASSIC)" in salida.mensaje
        assert "CENA SIBARITA" in salida.mensaje


# ══════════════════════════════════════════════════════════════════════════════
# FSM integration: Playa Linda with new price auto-calculates
# ══════════════════════════════════════════════════════════════════════════════


class TestPlayaLindaConPrecioAutoCalcula:
    """Tour 40 (PLAYA LINDA) with neto_adulto=55000 must NOT fall to MONTO_NETO."""

    def test_playa_linda_con_precio_va_a_participante_rol(self, fsm: FSMTiquetera) -> None:
        # 2 adults x 55000 = 110000; valor > neto -> routes to PARTICIPANTE_ROL
        ctx = ContextoVenta(
            destinos_numeros=[40],
            adultos=2,
            ninos=0,
            valor=Decimal("320000"),
        )
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_playa_linda_neto_calculado_correctamente(self, fsm: FSMTiquetera) -> None:
        # 3 adults x 55000 = 165000 (neto_nino=None -> child price treated as adult)
        ctx = ContextoVenta(
            destinos_numeros=[40],
            adultos=3,
            ninos=0,
            valor=Decimal("500000"),
        )
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.neto == Decimal("165000")
