"""Tests for valor_total property on ContextoCotizacion — SC-B01..SC-B06 (RED first)."""

from __future__ import annotations

from decimal import Decimal

from garay.aplicacion.cotizacion.contexto import ContextoCotizacion


class TestValorTotalProperty:
    """SC-B01 to SC-B06: exhaustive money calculation tests."""

    def test_calculo_completo(self) -> None:
        """SC-B01: adultos=2×150000 + ninos=1×80000 = 380000."""
        ctx = ContextoCotizacion(
            precio_adulto=Decimal("150000"),
            precio_nino=Decimal("80000"),
            adultos=2,
            ninos=1,
        )
        assert ctx.valor_total == Decimal("380000")

    def test_sin_ninos(self) -> None:
        """SC-B02: ninos=0 → only adultos count."""
        ctx = ContextoCotizacion(
            precio_adulto=Decimal("150000"),
            precio_nino=Decimal("80000"),
            adultos=3,
            ninos=0,
        )
        assert ctx.valor_total == Decimal("450000")

    def test_precio_nino_none_fallback(self) -> None:
        """SC-B03: precio_nino=None → treated as 0 even when ninos=2."""
        ctx = ContextoCotizacion(
            precio_adulto=Decimal("150000"),
            precio_nino=None,
            adultos=1,
            ninos=2,
        )
        assert ctx.valor_total == Decimal("150000")

    def test_precio_adulto_none_fallback(self) -> None:
        """SC-B04: precio_adulto=None → valor_total == 0."""
        ctx = ContextoCotizacion(
            precio_adulto=None,
            adultos=2,
            ninos=0,
        )
        assert ctx.valor_total == Decimal("0")

    def test_result_has_no_fractional_part(self) -> None:
        """SC-B05: valor_total is a whole Decimal (COP — no cents)."""
        ctx = ContextoCotizacion(
            precio_adulto=Decimal("150000"),
            adultos=2,
            ninos=0,
        )
        total = ctx.valor_total
        assert total == total.to_integral_value(), "valor_total must be a whole number"

    def test_result_is_decimal_not_float(self) -> None:
        """SC-B06: intermediates and result are Decimal, not float or int."""
        ctx = ContextoCotizacion(
            precio_adulto=Decimal("150000"),
            adultos=2,
            ninos=0,
        )
        total = ctx.valor_total
        assert isinstance(total, Decimal), f"Expected Decimal, got {type(total)}"
        assert not isinstance(total, float)
