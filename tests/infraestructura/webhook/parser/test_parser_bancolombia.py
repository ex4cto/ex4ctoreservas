"""Tests for ParserBancolombia — TDD RED phase."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.infraestructura.webhook.parser.bancolombia import ParserBancolombia
from garay.infraestructura.webhook.parser.base import ErrorParseoBanco

_PARSER = ParserBancolombia()

_TEXTO_VALIDO = (
    "recibiste una transferencia de Juan Perez por $1,500,000 "
    "el 15/07/26 a las 10:30"
)

_TEXTO_VALIDO_4_DIGITOS = (
    "recibiste una transferencia de Maria Lopez por $250,000.50 "
    "el 29/04/2026 a las 04:27"
)


def test_parsea_texto_valido_devuelve_pago_extraido() -> None:
    resultado = _PARSER.parsear(_TEXTO_VALIDO, _TEXTO_VALIDO)

    assert resultado.remitente == "Juan Perez"
    assert resultado.monto == Decimal("1500000")
    assert resultado.banco_origen == "Bancolombia"


def test_parsea_fecha_2_digitos_anio() -> None:
    resultado = _PARSER.parsear(_TEXTO_VALIDO, _TEXTO_VALIDO)

    assert resultado.fecha_pago.year == 2026
    assert resultado.fecha_pago.month == 7
    assert resultado.fecha_pago.day == 15
    assert resultado.fecha_pago.hour == 10
    assert resultado.fecha_pago.minute == 30


def test_parsea_fecha_4_digitos_anio() -> None:
    resultado = _PARSER.parsear(_TEXTO_VALIDO_4_DIGITOS, _TEXTO_VALIDO_4_DIGITOS)

    assert resultado.fecha_pago.year == 2026
    assert resultado.fecha_pago.month == 4
    assert resultado.fecha_pago.day == 29
    assert resultado.monto == Decimal("250000.50")


def test_usa_cuerpo_html_si_texto_vacio() -> None:
    html = "<p>recibiste una transferencia de Carlos Rios por $500,000 el 01/01/26 a las 09:00</p>"
    resultado = _PARSER.parsear(html, "")

    assert resultado.remitente == "Carlos Rios"
    assert resultado.monto == Decimal("500000")


def test_texto_sin_patron_lanza_error_parseo() -> None:
    with pytest.raises(ErrorParseoBanco, match="No se encontro patron"):
        _PARSER.parsear("Notificacion irrelevante", "Notificacion irrelevante")


def test_monto_invalido_lanza_error_parseo() -> None:
    # Edge case: letter where number expected — covered by regex not matching at all
    texto = "recibiste una transferencia de Ana por $ABC el 01/01/26 a las 09:00"
    with pytest.raises(ErrorParseoBanco):
        _PARSER.parsear(texto, texto)
