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

# FIX 1: Footer "Total ahorrado" after real Total — parser must return real amount.
# After whitespace collapse: "...Total COP 12,800 ... Total ahorrado este mes COP 50,000"
_TEXTO_FOOTER_TOTAL = (
    "Tu viaje con Uber\n"
    "31/07/2026\n"
    "Tarifa base  COP 11,000\n"
    "Propina  COP 1,800\n"
    "Total  COP 12,800\n"
    "-- Desglose --\n"
    "Tarifa dinamica  COP 2,000\n"
    "Total ahorrado este mes  COP 50,000\n"
)

# FIX 1: Negative sub-line adjacent to Total — must not be captured as monto.
# Parser should return the positive Total amount, not the negative adjustment.
_TEXTO_DESCUENTO_NEGATIVO = (
    "Tu viaje con Uber\n"
    "07/08/2026\n"
    "Tarifa base  COP 10,920\n"
    "Descuento  -COP 219\n"
    "Total  COP 10,700\n"
)

# FIX 4: 6-digit (million-range) amount
_TEXTO_MILLON = (
    "Tu viaje con Uber\n"
    "31/07/2026\n"
    "Tarifa  COP 1,183,000\n"
    "Total  COP 1,183,000\n"
)

# FIX 6: Unrelated date in footer PLUS real trip date — parser must return TRIP date.
_TEXTO_FECHA_PIE_PAGINA = (
    "Tu viaje con Uber\n"
    "31/07/2026\n"
    "Tarifa base  COP 9,000\n"
    "Total  COP 9,000\n"
    "Oferta valida hasta 01/01/2027\n"
)


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


# FIX 1 — amount anchoring: footer Total must not override real Total
def test_footer_total_no_sobreescribe_monto_real() -> None:
    """A promotional 'Total ahorrado' line after the real Total must NOT be captured."""
    resultado = _PARSER.parsear("", _TEXTO_FOOTER_TOTAL)
    assert resultado.monto == Decimal("12800")


# FIX 1 — negative sub-line must not be captured
def test_descuento_negativo_no_capturado() -> None:
    """A negative adjustment line adjacent to Total must not become the parsed monto."""
    resultado = _PARSER.parsear("", _TEXTO_DESCUENTO_NEGATIVO)
    assert resultado.monto == Decimal("10700")


# FIX 4 — 6-digit (million-range) amount
def test_monto_seis_digitos() -> None:
    """Amounts in the million range with double comma separator parse correctly."""
    resultado = _PARSER.parsear("", _TEXTO_MILLON)
    assert resultado.monto == Decimal("1183000")


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


# FIX 4 — self-documenting: day > 12 proves DD/MM order
def test_fecha_dia_mayor_que_12() -> None:
    """Day=31 is unambiguous proof that the format is DD/MM/YYYY, not MM/DD/YYYY."""
    resultado = _PARSER.parsear("", _TEXTO_MILLON)
    assert resultado.fecha_egreso.day == 31
    assert resultado.fecha_egreso.month == 7


# FIX 6 — footer date must not override trip date
def test_fecha_pie_pagina_no_sobreescribe_fecha_real() -> None:
    """An unrelated date in a footer must not replace the trip date."""
    resultado = _PARSER.parsear("", _TEXTO_FECHA_PIE_PAGINA)
    assert resultado.fecha_egreso.day == 31
    assert resultado.fecha_egreso.month == 7
    assert resultado.fecha_egreso.year == 2026


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_banco_origen_es_uber() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PRIORITY)
    assert resultado.banco_origen == BANCO_UBER


# FIX 5 — exact description string
def test_descripcion_exacta() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PRIORITY)
    assert resultado.descripcion == "Viaje Uber"


# ---------------------------------------------------------------------------
# HTML-only fallback
# ---------------------------------------------------------------------------


def test_html_only_parsea_correctamente() -> None:
    resultado = _PARSER.parsear(_HTML_PRIORITY, "")
    assert resultado.monto == Decimal("10700")
    assert resultado.banco_origen == BANCO_UBER


# ---------------------------------------------------------------------------
# Error path — FIX 2: failure branches (ErrorParseoBanco)
# ---------------------------------------------------------------------------


def test_sin_total_lanza_error() -> None:
    with pytest.raises(ErrorParseoBanco):
        _PARSER.parsear("", _TEXTO_SIN_TOTAL)


# FIX 2 — valid Total line but NO date -> must raise ErrorParseoBanco
def test_sin_fecha_lanza_error() -> None:
    """A body with a valid Total but no DD/MM/YYYY date must raise ErrorParseoBanco."""
    texto_sin_fecha = (
        "Tu viaje con Uber\n"
        "Tarifa base  COP 9,000\n"
        "Total  COP 10,700\n"
        "Gracias por viajar con Uber."
    )
    with pytest.raises(ErrorParseoBanco):
        _PARSER.parsear("", texto_sin_fecha)


# --- destinatario confirmation (REQ-1, Phase 8.1) ---

def test_uber_destinatario_es_none() -> None:
    """Uber trip charges have no payee recipient; destinatario must be None (REQ-1)."""
    resultado = _PARSER.parsear("", _TEXTO_PRIORITY)
    assert resultado.destinatario is None
