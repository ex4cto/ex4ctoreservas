"""Tests for the canonical Colombian peso amount parser."""

from __future__ import annotations

from decimal import Decimal

from garay.aplicacion.comun.montos import parsear_monto


class TestParsearMonto:
    def test_miles_shorthand_escala_x1000(self) -> None:
        """Plain numbers < 1000 are miles de pesos (Colombian everyday convention)."""
        assert parsear_monto("500") == Decimal("500000")
        assert parsear_monto("50") == Decimal("50000")
        assert parsear_monto("300") == Decimal("300000")

    def test_notacion_completa_no_escala(self) -> None:
        """Full notation (>= 1000) is respected as-is; dots are thousands separators."""
        assert parsear_monto("500.000") == Decimal("500000")
        assert parsear_monto("1800000") == Decimal("1800000")
        assert parsear_monto("1.800.000") == Decimal("1800000")
        assert parsear_monto("80000") == Decimal("80000")

    def test_frontera_1000_no_escala(self) -> None:
        """Exactly 1000 is not scaled; 999 still counts as miles shorthand."""
        assert parsear_monto("1000") == Decimal("1000")
        assert parsear_monto("999") == Decimal("999000")

    def test_espacios_se_recortan(self) -> None:
        assert parsear_monto("  300  ") == Decimal("300000")

    def test_cero_es_cero(self) -> None:
        assert parsear_monto("0") == Decimal("0")

    def test_negativo_es_none(self) -> None:
        assert parsear_monto("-500") is None

    def test_no_numerico_es_none(self) -> None:
        assert parsear_monto("abc") is None

    def test_vacio_es_none(self) -> None:
        assert parsear_monto("") is None
