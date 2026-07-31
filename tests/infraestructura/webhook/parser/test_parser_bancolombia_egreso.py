"""Tests for ParserBancolombiaEgreso — RED phase."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.infraestructura.webhook.parser.bancolombia_egreso import (
    ParserBancolombiaEgreso,
    _parsear_monto_bilingue,
)
from garay.infraestructura.webhook.parser.base import ErrorParseoBanco

_PARSER = ParserBancolombiaEgreso()

_TEXTO_COMPRA = (
    "Bancolombia: Compraste $69.328,00 en MOVISTAR PAGOSEPAYCO con tu T.Deb *9283, "
    "el 27/07/2026 a las 18:25."
)
_TEXTO_COMPRA_2 = (
    "Bancolombia: Compraste $10.000,00 en GAZEL EL TIGRE con tu T.Deb *9283, "
    "el 12/07/2026 a las 21:43."
)
_TEXTO_TRANSFERENCIA_CUENTA = (
    "Bancolombia: Transferiste $50,000.00 desde tu cuenta 7488 a la cuenta *3207904880 "
    "el 26/07/2026 a las 14:05."
)
_TEXTO_TRANSFERENCIA_BREB = (
    "Bancolombia: BRYAN, transferiste $6,000.00 a la llave 3015879983 desde tu cuenta *7488 "
    "a NEIDA GARCIA el 25/07/26 a las 16:26."
)


# --- monto bilingue ---

def test_monto_colombiano_punto_miles_coma_decimal() -> None:
    assert _parsear_monto_bilingue("$69.328,00") == Decimal("69328.00")


def test_monto_us_coma_miles_punto_decimal_grande() -> None:
    assert _parsear_monto_bilingue("$50,000.00") == Decimal("50000.00")


def test_monto_us_coma_miles_punto_decimal_pequeno() -> None:
    assert _parsear_monto_bilingue("$6,000.00") == Decimal("6000.00")


def test_monto_nequi_solo_puntos_miles() -> None:
    assert _parsear_monto_bilingue("5.000") == Decimal("5000")


def test_monto_numero_plano() -> None:
    assert _parsear_monto_bilingue("100") == Decimal("100")


def test_monto_colombiano_con_signo_sin_centavos() -> None:
    assert _parsear_monto_bilingue("$3.000") == Decimal("3000")


def test_monto_colombiano_punto_miles_sin_centavos_10k() -> None:
    assert _parsear_monto_bilingue("$10.000,00") == Decimal("10000.00")


# --- tipo 1: compra tarjeta debito ---

def test_parsea_compra_tarjeta_debito_monto() -> None:
    resultado = _PARSER.parsear("", _TEXTO_COMPRA)
    assert resultado.monto == Decimal("69328.00")


def test_parsea_compra_tarjeta_debito_descripcion() -> None:
    resultado = _PARSER.parsear("", _TEXTO_COMPRA)
    assert resultado.descripcion == "Compra en MOVISTAR PAGOSEPAYCO"


def test_parsea_compra_tarjeta_debito_banco_origen() -> None:
    resultado = _PARSER.parsear("", _TEXTO_COMPRA)
    assert resultado.banco_origen == "Bancolombia"


def test_parsea_compra_tarjeta_debito_fecha() -> None:
    resultado = _PARSER.parsear("", _TEXTO_COMPRA)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 7
    assert resultado.fecha_egreso.day == 27
    assert resultado.fecha_egreso.hour == 18
    assert resultado.fecha_egreso.minute == 25


def test_parsea_segunda_compra_tarjeta() -> None:
    resultado = _PARSER.parsear("", _TEXTO_COMPRA_2)
    assert resultado.monto == Decimal("10000.00")
    assert resultado.descripcion == "Compra en GAZEL EL TIGRE"


# --- tipo 2: transferencia a cuenta ---

def test_parsea_transferencia_cuenta_monto() -> None:
    resultado = _PARSER.parsear("", _TEXTO_TRANSFERENCIA_CUENTA)
    assert resultado.monto == Decimal("50000.00")


def test_parsea_transferencia_cuenta_descripcion() -> None:
    resultado = _PARSER.parsear("", _TEXTO_TRANSFERENCIA_CUENTA)
    assert resultado.descripcion == "Transferencia a cuenta *3207904880"


def test_parsea_transferencia_cuenta_origen_con_asterisco() -> None:
    """Source account may carry a '*' prefix: 'desde tu cuenta *5643'."""
    texto = (
        "Bancolombia: Transferiste $560,000 desde tu cuenta *5643 a la cuenta "
        "*08600002475 el 16/07/2026 a las 17:28."
    )
    resultado = _PARSER.parsear("", texto)
    assert resultado.monto == Decimal("560000")
    assert resultado.descripcion == "Transferencia a cuenta *08600002475"


def test_parsea_transferencia_cuenta_fecha() -> None:
    resultado = _PARSER.parsear("", _TEXTO_TRANSFERENCIA_CUENTA)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 7
    assert resultado.fecha_egreso.day == 26


# --- tipo 3: transferencia Bre-B / llave ---

def test_parsea_transferencia_breb_monto() -> None:
    resultado = _PARSER.parsear("", _TEXTO_TRANSFERENCIA_BREB)
    assert resultado.monto == Decimal("6000.00")


def test_parsea_transferencia_breb_descripcion() -> None:
    resultado = _PARSER.parsear("", _TEXTO_TRANSFERENCIA_BREB)
    assert resultado.descripcion == "Transferencia a NEIDA GARCIA"


def test_parsea_transferencia_breb_llave_con_arroba() -> None:
    """Bre-B keys can be @user (not only digits) — must still parse."""
    texto = (
        "Bancolombia: transferiste $6,000.00 a la llave @9019221257 desde tu cuenta *7488 "
        "a NEIDA GARCIA el 25/07/26 a las 16:26."
    )
    resultado = _PARSER.parsear("", texto)
    assert resultado.monto == Decimal("6000.00")
    assert resultado.descripcion == "Transferencia a NEIDA GARCIA"


def test_parsea_transferencia_breb_fecha_2_digitos() -> None:
    resultado = _PARSER.parsear("", _TEXTO_TRANSFERENCIA_BREB)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 7
    assert resultado.fecha_egreso.day == 25
    assert resultado.fecha_egreso.hour == 16
    assert resultado.fecha_egreso.minute == 26


# --- errores ---

def test_texto_sin_patron_lanza_error() -> None:
    with pytest.raises(ErrorParseoBanco, match="No se encontro patron"):
        _PARSER.parsear("", "Notificacion irrelevante sin datos de egreso")
