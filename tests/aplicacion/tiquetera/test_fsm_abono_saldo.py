"""TDD tests for bug fixes 2a (saldo pendiente) and 2b (abono guard vs valor).

RED phase: these tests MUST fail before the implementation is in place.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta

# ── Shared test catalog (same as test_fsm.py) ─────────────────────────────────
SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ", []),
    (2, "Tour Isla", Decimal("150000"), None, "ISLAS", []),
    (3, "City Tour", None, None, "ISLAS", []),
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


# ══════════════════════════════════════════════════════════════════════════════
# Bug 2b — Abono guard must compare against valor, not neto
# ══════════════════════════════════════════════════════════════════════════════


class TestAbonoGuardaContraValor:
    """_handle_monto_abono must reject abono > valor, regardless of neto."""

    def test_abono_mayor_que_valor_permanece_en_monto_abono(
        self, fsm: FSMTiquetera
    ) -> None:
        # valor=300000; abono=350000 > valor → stays at MONTO_ABONO
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=1,
            ninos=0,
            valor=Decimal("300000"),
        )
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "350000", ctx)
        assert salida.nuevo_estado == EstadoFSM.MONTO_ABONO

    def test_abono_mayor_que_valor_muestra_mensaje_error_abono_supera_valor(
        self, fsm: FSMTiquetera
    ) -> None:
        # Error message must reference "error_abono_supera_valor" key text
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=1,
            ninos=0,
            valor=Decimal("300000"),
        )
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "350000", ctx)
        # The new message contains abono amount and valor amount
        assert "$350.000" in salida.mensaje
        assert "$300.000" in salida.mensaje

    def test_regresion_abono_200k_valor_300k_neto_100k_ahora_avanza(
        self, fsm: FSMTiquetera
    ) -> None:
        """Regression: valor=300000, neto=100000 (service 1 x1 adult), abono=200000.

        Old behavior: wrongly rejected (abono 200k > neto 100k).
        New behavior: accepted (abono 200k <= valor 300k) → advances to PARTICIPANTE_ROL.
        """
        # Service 1: neto_adulto=100000 for 1 adult → neto=100000
        # valor=300000, abono=200000 (abono > neto=100000, but abono < valor=300000)
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=1,
            ninos=0,
            valor=Decimal("300000"),
        )
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "200000", ctx)
        # Must advance past MONTO_ABONO (to PARTICIPANTE_ROL)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_abono_igual_a_valor_es_valido(self, fsm: FSMTiquetera) -> None:
        # abono == valor → valid (full payment, zero balance) → advances
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=1,
            ninos=0,
            valor=Decimal("300000"),
        )
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "300000", ctx)
        assert salida.nuevo_estado != EstadoFSM.MONTO_ABONO

    def test_guarda_abono_corre_cuando_neto_es_none(self, fsm: FSMTiquetera) -> None:
        """Guard must fire against valor even when neto cannot be calculated.

        Service 3 has neto_adulto=None → _calcular_neto returns None.
        If abono > valor, must still reject with MONTO_ABONO, NOT fall through to MONTO_NETO.
        """
        ctx = ContextoVenta(
            destinos_numeros=[3],  # no price → neto=None
            adultos=1,
            ninos=0,
            valor=Decimal("200000"),
        )
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "250000", ctx)
        # abono=250000 > valor=200000 → reject, even though neto is None
        assert salida.nuevo_estado == EstadoFSM.MONTO_ABONO
        assert "$250.000" in salida.mensaje
        assert "$200.000" in salida.mensaje
