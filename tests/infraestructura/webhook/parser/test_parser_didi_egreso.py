"""Tests for ParserDiDiEgreso — RED phase."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.infraestructura.webhook.parser.base import BANCO_DIDI, ErrorParseoBanco
from garay.infraestructura.webhook.parser.didi_egreso import ParserDiDiEgreso

_PARSER = ParserDiDiEgreso()

# ---------------------------------------------------------------------------
# Inline fixture bodies — real sample shapes
# ---------------------------------------------------------------------------

# DiDi Express receipt: dot as thousands separator, no decimals
_TEXTO_EXPRESS = (
    "Tu viaje DiDi\n"
    "DiDi Express\n"
    "vie, 31 jul, 2026\n"
    "Tarifa base  $11.500\n"
    "Propina  $1.300\n"
    "Total  $12.800\n"
    "Gracias por viajar con DiDi."
)

# DiDi Pon Tu Precio receipt
_TEXTO_PON_TU_PRECIO = (
    "Tu viaje DiDi\n"
    "Pon Tu Precio\n"
    "lun, 10 ago, 2026\n"
    "Tarifa  $9.200\n"
    "Descuento  -$300\n"
    "Total  $9.500\n"
)

# DiDi Moto receipt
_TEXTO_MOTO = (
    "Tu viaje DiDi\n"
    "DiDi Moto\n"
    "mar, 5 may, 2026\n"
    "Tarifa  $9.500\n"
    "Total  $9.500\n"
)

# HTML-only body (texto == "")
_HTML_EXPRESS = (
    "<html><body>"
    "<p>Tu viaje DiDi</p>"
    "<p>vie, 31 jul, 2026</p>"
    "<p>Tarifa base &nbsp; $11.500</p>"
    "<p>Total &nbsp; $12.800</p>"
    "</body></html>"
)

# Body with no Total line -> should raise
_TEXTO_SIN_TOTAL = "Tu viaje DiDi\nGracias por viajar."

# FIX 1: Footer "Total ahorrado" after real Total — parser must return real amount.
_TEXTO_FOOTER_TOTAL = (
    "Tu viaje DiDi\n"
    "DiDi Express\n"
    "vie, 31 jul, 2026\n"
    "Tarifa base  $11.500\n"
    "Propina  $1.300\n"
    "Total  $12.800\n"
    "-- Desglose --\n"
    "Tarifa dinamica  $2.000\n"
    "Total ahorrado este mes  $50.000\n"
)

# FIX 1: Negative sub-line adjacent to Total — must not be captured as monto.
_TEXTO_DESCUENTO_NEGATIVO = (
    "Tu viaje DiDi\n"
    "DiDi Express\n"
    "vie, 31 jul, 2026\n"
    "Tarifa base  $13.400\n"
    "Descuento  -$2.600\n"
    "Total  $12.800\n"
)

# FIX 4: 6-digit (million-range) amount
_TEXTO_MILLON = (
    "Tu viaje DiDi\n"
    "DiDi Express\n"
    "vie, 31 jul, 2026\n"
    "Tarifa  $1.183.000\n"
    "Total  $1.183.000\n"
)

# FIX 2: No date (garbage/unknown month) but valid Total -> ErrorParseoBanco
_TEXTO_MES_DESCONOCIDO = (
    "Tu viaje DiDi\n"
    "DiDi Express\n"
    "vie, 31 xyz, 2026\n"
    "Tarifa base  $11.500\n"
    "Total  $12.800\n"
)


# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------


def test_express_monto() -> None:
    resultado = _PARSER.parsear("", _TEXTO_EXPRESS)
    assert resultado.monto == Decimal("12800")


def test_pon_tu_precio_monto() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PON_TU_PRECIO)
    assert resultado.monto == Decimal("9500")


def test_moto_monto() -> None:
    resultado = _PARSER.parsear("", _TEXTO_MOTO)
    assert resultado.monto == Decimal("9500")


# FIX 1 — amount anchoring: footer Total must not override real Total
def test_footer_total_no_sobreescribe_monto_real() -> None:
    """A promotional 'Total ahorrado' line after the real Total must NOT be captured."""
    resultado = _PARSER.parsear("", _TEXTO_FOOTER_TOTAL)
    assert resultado.monto == Decimal("12800")


# FIX 1 — negative sub-line must not be captured
def test_descuento_negativo_no_capturado() -> None:
    """A negative adjustment line adjacent to Total must not become the parsed monto."""
    resultado = _PARSER.parsear("", _TEXTO_DESCUENTO_NEGATIVO)
    assert resultado.monto == Decimal("12800")


# FIX 4 — 6-digit (million-range) amount
def test_monto_seis_digitos() -> None:
    """Amounts in the million range with dot separator parse correctly."""
    resultado = _PARSER.parsear("", _TEXTO_MILLON)
    assert resultado.monto == Decimal("1183000")


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


def test_express_fecha() -> None:
    resultado = _PARSER.parsear("", _TEXTO_EXPRESS)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 7
    assert resultado.fecha_egreso.day == 31


def test_pon_tu_precio_fecha() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PON_TU_PRECIO)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 8
    assert resultado.fecha_egreso.day == 10


def test_moto_fecha() -> None:
    resultado = _PARSER.parsear("", _TEXTO_MOTO)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 5
    assert resultado.fecha_egreso.day == 5


def test_fecha_es_utc() -> None:
    from datetime import UTC

    resultado = _PARSER.parsear("", _TEXTO_EXPRESS)
    assert resultado.fecha_egreso.tzinfo is UTC


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_banco_origen_es_didi() -> None:
    resultado = _PARSER.parsear("", _TEXTO_EXPRESS)
    assert resultado.banco_origen == BANCO_DIDI


# FIX 5 — exact description string
def test_descripcion_exacta() -> None:
    resultado = _PARSER.parsear("", _TEXTO_EXPRESS)
    assert resultado.descripcion == "Viaje DiDi"


# ---------------------------------------------------------------------------
# HTML-only fallback
# ---------------------------------------------------------------------------


def test_html_only_parsea_correctamente() -> None:
    resultado = _PARSER.parsear(_HTML_EXPRESS, "")
    assert resultado.monto == Decimal("12800")
    assert resultado.banco_origen == BANCO_DIDI


# ---------------------------------------------------------------------------
# Error path — FIX 2: failure branches (ErrorParseoBanco)
# ---------------------------------------------------------------------------


def test_sin_total_lanza_error() -> None:
    with pytest.raises(ErrorParseoBanco):
        _PARSER.parsear("", _TEXTO_SIN_TOTAL)


# FIX 2 — garbage/unknown month -> must raise ErrorParseoBanco
def test_mes_desconocido_lanza_error() -> None:
    """A date with an unknown Spanish month abbreviation must raise ErrorParseoBanco."""
    with pytest.raises(ErrorParseoBanco):
        _PARSER.parsear("", _TEXTO_MES_DESCONOCIDO)
