"""Tests for ParserUberEgreso — RED phase."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.infraestructura.webhook.parser.base import BANCO_UBER, ErrorParseoBanco
from garay.infraestructura.webhook.parser.uber_egreso import ParserUberEgreso

_PARSER = ParserUberEgreso()

# ---------------------------------------------------------------------------
# Inline fixture bodies — real sample shapes
# ---------------------------------------------------------------------------

# Uber Priority receipt: COP comma-thousands, date DD/MM/YYYY
_TEXTO_PRIORITY = (
    "Tu viaje con Uber\n"
    "Uber Priority\n"
    "07/08/2026\n"
    "Tarifa base  COP 9,000\n"
    "Propina  COP 1,000\n"
    "Total  COP 10,700\n"
    "Gracias por viajar con Uber."
)

# Uber Economy receipt
_TEXTO_ECONOMY = (
    "Tu viaje con Uber\n"
    "Uber Economy\n"
    "10/08/2026\n"
    "Tarifa base  COP 8,500\n"
    "Total  COP 8,500\n"
)

# Uber Priority with toll/adjustment lines above Total
_TEXTO_CON_PEAJE = (
    "Tu viaje con Uber\n"
    "07/08/2026\n"
    "Tarifa base  COP 8,000\n"
    "Peaje  COP 2,000\n"
    "Descuento  -COP 300\n"
    "Total  COP 10,700\n"
)

# HTML-only body (texto == "")
_HTML_PRIORITY = (
    "<html><body>"
    "<p>Tu viaje con Uber</p>"
    "<p>07/08/2026</p>"
    "<p>Tarifa base &nbsp; COP 9,000</p>"
    "<p>Total &nbsp; COP 10,700</p>"
    "</body></html>"
)

# Body with no Total line -> should raise
_TEXTO_SIN_TOTAL = "Tu viaje con Uber\nGracias por viajar."


# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------


def test_priority_monto() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PRIORITY)
    assert resultado.monto == Decimal("10700")


def test_economy_monto() -> None:
    resultado = _PARSER.parsear("", _TEXTO_ECONOMY)
    assert resultado.monto == Decimal("8500")


def test_monto_con_peaje_usa_total_no_subtotal() -> None:
    """Toll/adjustment lines above Total must not affect the parsed amount."""
    resultado = _PARSER.parsear("", _TEXTO_CON_PEAJE)
    assert resultado.monto == Decimal("10700")


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


def test_priority_fecha() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PRIORITY)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 8
    assert resultado.fecha_egreso.day == 7


def test_economy_fecha() -> None:
    resultado = _PARSER.parsear("", _TEXTO_ECONOMY)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 8
    assert resultado.fecha_egreso.day == 10


def test_fecha_es_utc() -> None:
    from datetime import UTC

    resultado = _PARSER.parsear("", _TEXTO_PRIORITY)
    assert resultado.fecha_egreso.tzinfo is UTC


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_banco_origen_es_uber() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PRIORITY)
    assert resultado.banco_origen == BANCO_UBER


def test_descripcion_sensata() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PRIORITY)
    assert resultado.descripcion != ""


# ---------------------------------------------------------------------------
# HTML-only fallback
# ---------------------------------------------------------------------------


def test_html_only_parsea_correctamente() -> None:
    resultado = _PARSER.parsear(_HTML_PRIORITY, "")
    assert resultado.monto == Decimal("10700")
    assert resultado.banco_origen == BANCO_UBER


# ---------------------------------------------------------------------------
# Error path
# ---------------------------------------------------------------------------


def test_sin_total_lanza_error() -> None:
    with pytest.raises(ErrorParseoBanco):
        _PARSER.parsear("", _TEXTO_SIN_TOTAL)
