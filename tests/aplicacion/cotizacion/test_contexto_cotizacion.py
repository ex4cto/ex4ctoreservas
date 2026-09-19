"""Tests for ContextoCotizacion — SC-A01, SC-A02, SC-A03 (RED first, TDD)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.aplicacion.cotizacion.contexto import ContextoCotizacion


class TestContextoCotizacionDefaults:
    """SC-A01: ContextoCotizacion() instantiated with no args has correct defaults."""

    def test_ninos_default_cero(self) -> None:
        ctx = ContextoCotizacion()
        assert ctx.ninos == 0

    def test_factura_idioma_default_es(self) -> None:
        ctx = ContextoCotizacion()
        assert ctx.factura_idioma == "es"

    def test_sin_hotel_default_true(self) -> None:
        ctx = ContextoCotizacion()
        assert ctx.sin_hotel is True

    def test_cliente_email_default_none(self) -> None:
        ctx = ContextoCotizacion()
        assert ctx.cliente_email is None

    def test_precio_adulto_default_none(self) -> None:
        ctx = ContextoCotizacion()
        assert ctx.precio_adulto is None


class TestContextoCotizacionTypeGuard:
    """SC-A02: precio_adulto/precio_nino must be Decimal, not float."""

    def test_precio_adulto_float_lanza_type_error(self) -> None:
        with pytest.raises(TypeError):
            ContextoCotizacion(precio_adulto=150000.0)  # type: ignore[arg-type]

    def test_precio_nino_float_lanza_type_error(self) -> None:
        with pytest.raises(TypeError):
            ContextoCotizacion(precio_nino=80000.0)  # type: ignore[arg-type]

    def test_precio_adulto_decimal_acepta(self) -> None:
        """SC-A03: Decimal is accepted without error."""
        ctx = ContextoCotizacion(precio_adulto=Decimal("150000"))
        assert ctx.precio_adulto == Decimal("150000")

    def test_precio_nino_decimal_acepta(self) -> None:
        ctx = ContextoCotizacion(precio_nino=Decimal("80000"))
        assert ctx.precio_nino == Decimal("80000")
