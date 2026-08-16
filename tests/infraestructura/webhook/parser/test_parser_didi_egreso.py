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


def test_descripcion_sensata() -> None:
    resultado = _PARSER.parsear("", _TEXTO_EXPRESS)
    assert resultado.descripcion != ""


# ---------------------------------------------------------------------------
# HTML-only fallback
# ---------------------------------------------------------------------------


def test_html_only_parsea_correctamente() -> None:
    resultado = _PARSER.parsear(_HTML_EXPRESS, "")
    assert resultado.monto == Decimal("12800")
    assert resultado.banco_origen == BANCO_DIDI


# ---------------------------------------------------------------------------
# Error path
# ---------------------------------------------------------------------------


def test_sin_total_lanza_error() -> None:
    with pytest.raises(ErrorParseoBanco):
        _PARSER.parsear("", _TEXTO_SIN_TOTAL)
