"""TDD tests for bug fix 2a: saldo pendiente shown in confirmation summary.

RED phase: these tests MUST fail before the implementation is in place.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta

# ── Shared test catalog (same as test_fsm.py) ─────────────────────────────────
SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ"),
    (2, "Tour Isla", Decimal("150000"), None, "ISLAS"),
    (3, "City Tour", None, None, "ISLAS"),
]
PUNTOS_TEST: list[str] = ["Marie Real", "Mama Waldi"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


# ══════════════════════════════════════════════════════════════════════════════
# Bug 2a — Saldo pendiente shown in confirmation summary
# ══════════════════════════════════════════════════════════════════════════════


class TestSaldoPendienteEnResumen:
    """_construir_resumen must include a 'Saldo pendiente:' line = valor - abono."""

    def test_resumen_incluye_saldo_pendiente_con_valor_y_abono(
        self, fsm: FSMTiquetera
    ) -> None:
        # valor=300000, abono=100000 → saldo=200000
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=1,
            ninos=0,
            valor=Decimal("300000"),
            abono=Decimal("100000"),
            rol_registrante="ambos",
        )
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert "Saldo pendiente:" in salida.mensaje
        assert "$200.000" in salida.mensaje

    def test_resumen_saldo_pendiente_es_valor_cuando_abono_es_none(
        self, fsm: FSMTiquetera
    ) -> None:
        # abono=None → saldo = valor
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=1,
            ninos=0,
            valor=Decimal("300000"),
            abono=None,
            rol_registrante="ambos",
        )
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert "Saldo pendiente:" in salida.mensaje
        assert "$300.000" in salida.mensaje

    def test_resumen_saldo_pendiente_es_guion_cuando_valor_es_none(
        self, fsm: FSMTiquetera
    ) -> None:
        # valor=None → saldo shows "—"
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=1,
            ninos=0,
            valor=None,
            abono=None,
            rol_registrante="ambos",
        )
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert "Saldo pendiente:" in salida.mensaje
        # When valor is None, saldo_pendiente is None → _formatear_monto → "—"
        assert "Saldo pendiente: —" in salida.mensaje
