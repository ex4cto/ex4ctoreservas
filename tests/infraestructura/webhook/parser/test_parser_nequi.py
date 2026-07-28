"""Tests for ParserNequi — TDD RED phase."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.infraestructura.webhook.parser.base import ErrorParseoBanco
from garay.infraestructura.webhook.parser.nequi import ParserNequi

_PARSER = ParserNequi()

_TEXTO_VALIDO = "Recibiste 50.000 de Andrés García el 29 de abril de 2026 a las 4:27 p.m."

_TEXTO_SIN_DECIMAL = "Recibiste 100.000 de Maria Torres el 10 de julio de 2026 a las 11:00 a.m."


def test_parsea_texto_valido() -> None:
    resultado = _PARSER.parsear("", _TEXTO_VALIDO)

    assert resultado.remitente == "Andrés García"
    assert resultado.monto == Decimal("50000.00")
    assert resultado.banco_origen == "Nequi"
    assert resultado.fecha_pago.year == 2026
    assert resultado.fecha_pago.month == 4
    assert resultado.fecha_pago.day == 29
    assert resultado.fecha_pago.hour == 16
    assert resultado.fecha_pago.minute == 27


def test_parsea_hora_am() -> None:
    resultado = _PARSER.parsear("", _TEXTO_SIN_DECIMAL)

    assert resultado.fecha_pago.hour == 11
    assert resultado.fecha_pago.minute == 0
    assert resultado.monto == Decimal("100000.00")


def test_12pm_es_mediodia() -> None:
    texto = "Recibiste 20.000 de Luis Paz el 1 de enero de 2026 a las 12:00 p.m."
    resultado = _PARSER.parsear("", texto)
    assert resultado.fecha_pago.hour == 12


def test_12am_es_medianoche() -> None:
    texto = "Recibiste 20.000 de Luis Paz el 1 de enero de 2026 a las 12:00 a.m."
    resultado = _PARSER.parsear("", texto)
    assert resultado.fecha_pago.hour == 0


def test_texto_sin_patron_lanza_error_parseo() -> None:
    with pytest.raises(ErrorParseoBanco, match="No se encontro patron"):
        _PARSER.parsear("", "Transaccion fallida sin formato reconocido")
