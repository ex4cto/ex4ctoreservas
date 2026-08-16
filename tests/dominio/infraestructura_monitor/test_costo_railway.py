"""Tests for pure Railway cost domain functions.

Covers:
- PreciosRailway value object: frozen dataclass with 4 unit prices
- costo_uso: resource dict -> cost sum; unknown keys ignored; empty dict -> 0
- costo_factura: max(plan_fee, costo_uso)
- cruza_umbral: stateless once-only crossing (previo < umbral <= actual)
"""

from __future__ import annotations

import pytest

from garay.dominio.infraestructura_monitor.costo_railway import (
    PreciosRailway,
    costo_factura,
    costo_uso,
    cruza_umbral,
)

# ---------------------------------------------------------------------------
# Standard prices used across most tests (matches owner dashboard values)
# ---------------------------------------------------------------------------

_PRECIOS = PreciosRailway(
    precio_memoria_gb_min=0.000231,
    precio_cpu_vcpu_min=0.000463,
    precio_egress_gb=0.05,
    precio_volumen_gb_min=0.000003,
)


# ---------------------------------------------------------------------------
# PreciosRailway value object
# ---------------------------------------------------------------------------


class TestPreciosRailway:
    def test_es_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):
            _PRECIOS.precio_memoria_gb_min = 99.0  # type: ignore[misc]

    def test_igualdad_por_valor(self) -> None:
        a = PreciosRailway(0.000231, 0.000463, 0.05, 0.000003)
        b = PreciosRailway(0.000231, 0.000463, 0.05, 0.000003)
        assert a == b


# ---------------------------------------------------------------------------
# costo_uso
# ---------------------------------------------------------------------------


class TestCostoUso:
    def test_suma_cuatro_mediciones_conocidas(self) -> None:
        """All four known measurements contribute to the sum."""
        recursos = {
            "MEMORY_USAGE_GB": 1000.0,  # 1000 * 0.000231 = 0.231
            "CPU_USAGE": 1000.0,  # 1000 * 0.000463 = 0.463
            "NETWORK_TX_GB": 1.0,  # 1    * 0.05    = 0.05
            "DISK_USAGE_GB": 1000.0,  # 1000 * 0.000003 = 0.003
        }
        result = costo_uso(recursos, _PRECIOS)
        assert result == pytest.approx(0.231 + 0.463 + 0.05 + 0.003)

    def test_dict_vacio_retorna_cero(self) -> None:
        """Empty resource dict yields cost = 0."""
        result = costo_uso({}, _PRECIOS)
        assert result == pytest.approx(0.0)

    def test_medicion_desconocida_ignorada(self) -> None:
        """Unknown measurement keys must not contribute to cost."""
        recursos = {
            "MEMORY_USAGE_GB": 1000.0,
            "UNKNOWN_METRIC": 9999.0,  # must be ignored
        }
        result = costo_uso(recursos, _PRECIOS)
        assert result == pytest.approx(1000.0 * 0.000231)

    def test_solo_memoria(self) -> None:
        """Single-metric dict: only memory cost computed."""
        recursos = {"MEMORY_USAGE_GB": 500.0}
        result = costo_uso(recursos, _PRECIOS)
        assert result == pytest.approx(500.0 * 0.000231)

    def test_solo_egress(self) -> None:
        """Single-metric dict: only egress cost."""
        recursos = {"NETWORK_TX_GB": 2.0}
        result = costo_uso(recursos, _PRECIOS)
        assert result == pytest.approx(2.0 * 0.05)

    def test_valor_cero_en_medicion(self) -> None:
        """A measurement present with value 0 contributes nothing."""
        recursos = {"MEMORY_USAGE_GB": 0.0, "CPU_USAGE": 1000.0}
        result = costo_uso(recursos, _PRECIOS)
        assert result == pytest.approx(1000.0 * 0.000463)


# ---------------------------------------------------------------------------
# costo_factura
# ---------------------------------------------------------------------------


class TestCostoFactura:
    def test_retorna_costo_uso_cuando_supera_plan_fee(self) -> None:
        """Usage above plan fee: bill = usage."""
        result = costo_factura(costo_uso_val=10.0, plan_fee=5.0)
        assert result == pytest.approx(10.0)

    def test_retorna_plan_fee_cuando_uso_es_menor(self) -> None:
        """Usage below plan fee: bill = plan_fee (hobby floor)."""
        result = costo_factura(costo_uso_val=2.0, plan_fee=5.0)
        assert result == pytest.approx(5.0)

    def test_retorna_plan_fee_cuando_uso_es_igual(self) -> None:
        """Usage == plan fee: bill = plan_fee (max of two equal values)."""
        result = costo_factura(costo_uso_val=5.0, plan_fee=5.0)
        assert result == pytest.approx(5.0)

    def test_uso_cero_retorna_plan_fee(self) -> None:
        """Zero usage always floors to plan fee."""
        result = costo_factura(costo_uso_val=0.0, plan_fee=5.0)
        assert result == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# cruza_umbral
# ---------------------------------------------------------------------------


class TestCruzaUmbral:
    # previo < umbral <= actual → crossing fires

    def test_cruce_exacto_en_limite(self) -> None:
        """actual == umbral, previo < umbral: crossing fires."""
        assert cruza_umbral(actual=20.0, previo=19.99, umbral=20.0) is True

    def test_cruce_superando_limite(self) -> None:
        """actual > umbral, previo < umbral: crossing fires."""
        assert cruza_umbral(actual=25.0, previo=15.0, umbral=20.0) is True

    # No crossing below threshold

    def test_ambos_por_debajo_no_dispara(self) -> None:
        """Both actual and previo below threshold: no crossing."""
        assert cruza_umbral(actual=15.0, previo=10.0, umbral=20.0) is False

    def test_actual_justo_debajo_no_dispara(self) -> None:
        """actual == umbral - epsilon, previo below: not a crossing."""
        assert cruza_umbral(actual=19.99, previo=15.0, umbral=20.0) is False

    # Already above: no re-fire

    def test_ya_estaba_encima_no_dispara_de_nuevo(self) -> None:
        """previo already at umbral: moving further up does not re-fire."""
        assert cruza_umbral(actual=25.0, previo=20.0, umbral=20.0) is False

    def test_previo_mayor_al_umbral_no_dispara(self) -> None:
        """previo > umbral: already crossed before, no re-fire."""
        assert cruza_umbral(actual=30.0, previo=22.0, umbral=20.0) is False

    # Month-boundary reset: previo=0 re-enables crossing

    def test_mes_nuevo_previo_cero_cruza(self) -> None:
        """Fresh month (previo=0): if actual crosses umbral, fires correctly."""
        assert cruza_umbral(actual=21.0, previo=0.0, umbral=20.0) is True

    def test_mes_nuevo_previo_cero_sin_cruce(self) -> None:
        """Fresh month (previo=0): actual below umbral — no crossing."""
        assert cruza_umbral(actual=5.0, previo=0.0, umbral=20.0) is False
