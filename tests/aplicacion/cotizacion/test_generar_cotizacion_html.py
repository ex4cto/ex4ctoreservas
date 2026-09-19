"""Tests for GenerarCotizacionService — SC-C01 to SC-C22 (RED first, TDD)."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.aplicacion.cotizacion.contexto import ContextoCotizacion
from garay.aplicacion.cotizacion.servicio import GenerarCotizacionService


def _ctx_minimo() -> ContextoCotizacion:
    """Minimal valid context for most HTML tests."""
    return ContextoCotizacion(
        cliente_nombre="Test",
        destinos_nombres=["Tour Test"],
        fecha_salida=datetime.datetime(2026, 9, 20),
        adultos=2,
        precio_adulto=Decimal("150000"),
        ninos=0,
    )


@pytest.fixture
def svc() -> GenerarCotizacionService:
    return GenerarCotizacionService()


class TestReturnType:
    def test_returns_non_empty_string(self, svc: GenerarCotizacionService) -> None:
        """SC-C01: generar returns a non-empty string."""
        html = svc.generar(_ctx_minimo())
        assert isinstance(html, str)
        assert len(html) > 100


class TestTitles:
    def test_es_title(self, svc: GenerarCotizacionService) -> None:
        """SC-C02: ES title is 'COTIZACIÓN DE SERVICIO'."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "es"
        html = svc.generar(ctx)
        assert "COTIZACIÓN DE SERVICIO" in html

    def test_en_title(self, svc: GenerarCotizacionService) -> None:
        """SC-C03: EN title is 'SERVICE QUOTE'."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "en"
        html = svc.generar(ctx)
        assert "SERVICE QUOTE" in html

    def test_no_factura_title(self, svc: GenerarCotizacionService) -> None:
        """SC-C04: Neither factura title appears."""
        ctx = _ctx_minimo()
        html = svc.generar(ctx)
        assert "FACTURA DE SERVICIO" not in html
        assert "SERVICE INVOICE" not in html


class TestNoPaymentBlock:
    def test_no_payment_methods_block(self, svc: GenerarCotizacionService) -> None:
        """SC-C05: Payment methods block is absent."""
        html = svc.generar(_ctx_minimo())
        assert "BRE-B" not in html
        assert "@garay58804" not in html
        assert "085-043956-43" not in html


class TestNoAbonoRows:
    def test_no_abono_saldo_rows(self, svc: GenerarCotizacionService) -> None:
        """SC-C06: Abono/anticipo financial concept rows are absent.

        The words may appear in policy text (expected), but NOT as financial
        table row labels.
        """
        html = svc.generar(_ctx_minimo())
        # Financial row labels must not appear (they live in td/th cells)
        assert "Abono / anticipo" not in html
        assert "concepto_abono" not in html
        assert "Saldo pendiente" not in html
        assert "Balance due" not in html


class TestFinancialRow:
    def test_valor_total_formatted(self, svc: GenerarCotizacionService) -> None:
        """SC-C07: Single financial row shows valor_total in COP format."""
        ctx = _ctx_minimo()  # adultos=2 x 150000 = 300000
        html = svc.generar(ctx)
        assert "$300.000" in html


class TestClientBox:
    def test_nombre_and_email_present(self, svc: GenerarCotizacionService) -> None:
        """SC-C08: Client box shows nombre and email."""
        ctx = _ctx_minimo()
        ctx.cliente_nombre = "María García"
        ctx.cliente_email = "mg@test.com"
        html = svc.generar(ctx)
        assert "María García" in html
        assert "mg@test.com" in html

    def test_email_none_shows_dash(self, svc: GenerarCotizacionService) -> None:
        """SC-C09: Client box shows '—' when email is None."""
        ctx = _ctx_minimo()
        ctx.cliente_nombre = "Pedro"
        ctx.cliente_email = None
        html = svc.generar(ctx)
        assert "Pedro" in html
        assert "—" in html


class TestFooterText:
    def test_es_footer(self, svc: GenerarCotizacionService) -> None:
        """SC-C10: ES footer mentions 'cotización de servicio'."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "es"
        html = svc.generar(ctx)
        assert "cotización de servicio" in html.lower()

    def test_en_footer(self, svc: GenerarCotizacionService) -> None:
        """SC-C11: EN footer mentions 'service quote'."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "en"
        html = svc.generar(ctx)
        assert "service quote" in html.lower()


class TestCancellationPolicies:
    def test_es_has_fuerza_mayor(self, svc: GenerarCotizacionService) -> None:
        """SC-C12 ES: FUERZA MAYOR appears."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "es"
        html = svc.generar(ctx)
        assert "FUERZA MAYOR" in html or "fuerza mayor" in html.lower()

    def test_en_has_force_majeure(self, svc: GenerarCotizacionService) -> None:
        """SC-C12 EN: FORCE MAJEURE appears."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "en"
        html = svc.generar(ctx)
        assert "FORCE MAJEURE" in html or "force majeure" in html.lower()


class TestLayout:
    def test_page_break_present(self, svc: GenerarCotizacionService) -> None:
        """SC-C13: Two-page layout has page-break."""
        html = svc.generar(_ctx_minimo())
        assert "page-break" in html

    def test_nit_present(self, svc: GenerarCotizacionService) -> None:
        """SC-C14: NIT appears in company bar."""
        html = svc.generar(_ctx_minimo())
        assert "1128049588-6" in html


class TestLangAttribute:
    def test_lang_en(self, svc: GenerarCotizacionService) -> None:
        """SC-C15: lang='en' when factura_idioma='en'."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "en"
        html = svc.generar(ctx)
        assert 'lang="en"' in html

    def test_lang_es(self, svc: GenerarCotizacionService) -> None:
        """SC-C15: lang='es' when factura_idioma='es'."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "es"
        html = svc.generar(ctx)
        assert 'lang="es"' in html

    def test_invalid_idioma_defaults_to_es(self, svc: GenerarCotizacionService) -> None:
        """SC-C16: Invalid idioma 'fr' falls back to 'es'."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "fr"
        html = svc.generar(ctx)
        assert 'lang="es"' in html
        assert "COTIZACIÓN DE SERVICIO" in html


class TestEnglishPolicies:
    def test_en_has_spanish_prevails_notice(self, svc: GenerarCotizacionService) -> None:
        """SC-C17: EN HTML includes 'Spanish shall prevail' clause."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "en"
        html = svc.generar(ctx)
        assert "Spanish" in html
        assert "prevail" in html.lower()


class TestServiceDetailBox:
    def test_tour_name_present(self, svc: GenerarCotizacionService) -> None:
        """SC-C18: destinos_nombres appear in service detail."""
        ctx = _ctx_minimo()
        ctx.destinos_nombres = ["Islas del Rosario"]
        html = svc.generar(ctx)
        assert "Islas del Rosario" in html

    def test_date_formatted(self, svc: GenerarCotizacionService) -> None:
        """SC-C19: Date appears as DD/MM/YYYY."""
        ctx = _ctx_minimo()
        ctx.fecha_salida = datetime.datetime(2026, 9, 20)
        html = svc.generar(ctx)
        assert "20/09/2026" in html

    def test_adultos_ninos_count(self, svc: GenerarCotizacionService) -> None:
        """SC-C20: adultos and ninos counts appear."""
        ctx = _ctx_minimo()
        ctx.adultos = 3
        ctx.ninos = 2
        html = svc.generar(ctx)
        assert "3" in html
        assert "2" in html

    def test_hotel_es_sin_hotel(self, svc: GenerarCotizacionService) -> None:
        """SC-C21 ES: Hotel row always 'Sin hotel'."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "es"
        html = svc.generar(ctx)
        assert "Sin hotel" in html

    def test_hotel_en_no_hotel(self, svc: GenerarCotizacionService) -> None:
        """SC-C21 EN: Hotel row always 'No hotel'."""
        ctx = _ctx_minimo()
        ctx.factura_idioma = "en"
        html = svc.generar(ctx)
        assert "No hotel" in html

    def test_vendedor_nombre_present(self, svc: GenerarCotizacionService) -> None:
        """SC-C22: vendedor_nombre appears in asesor row."""
        ctx = _ctx_minimo()
        ctx.vendedor_nombre = "Carlos Garay"
        html = svc.generar(ctx)
        assert "Carlos Garay" in html
