"""Tests for ParserPSEEgreso — RED phase."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.infraestructura.webhook.parser.base import (
    ErrorParseoBanco,
    detectar_banco,
    detectar_direccion,
)
from garay.infraestructura.webhook.parser.fabrica import obtener_parser_egreso
from garay.infraestructura.webhook.parser.pse_egreso import ParserPSEEgreso

_PARSER = ParserPSEEgreso()

# Real PSE email fixture (clean text)
_TEXTO_PSE = (
    "PSE - Transacción Aprobada ✅ CUS 455692497\n"
    "De: serviciopse@achcolombia.com.co\n"
    "¡Hola, Julio Cesar Garay Manzur!\n"
    " Los siguientes son los datos de tu transacción:\n"
    "Valor: $ 124.200,00\n"
    "Empresa: WOMPI S.A.S\n"
    "Descripción: Sent from PayJoy PaymentOptionsProvidersSDK.\n"
    "Fecha de la transacción: 06/07/2026\n"
    "CUS: 455692497\n"
    "Gracias por utilizar nuestro servicio.\n"
)

# Variant with NBSP (\xa0) and extra line breaks — must parse identically
_TEXTO_PSE_NBSP = (
    "PSE\xa0-\xa0Transacción\xa0Aprobada\xa0✅\xa0CUS\xa0455692497\n"
    "De:\xa0serviciopse@achcolombia.com.co\n"
    "¡Hola,\xa0Julio\xa0Cesar\xa0Garay\xa0Manzur!\n"
    "\xa0Los\xa0siguientes\xa0son\xa0los\xa0datos\xa0de\xa0tu\xa0transacción:\n"
    "Valor:\xa0$\xa0124.200,00\n"
    "Empresa:\xa0WOMPI\xa0S.A.S\n"
    "Descripción:\xa0Sent\xa0from\xa0PayJoy\xa0PaymentOptionsProvidersSDK.\n"
    "Fecha\xa0de\xa0la\xa0transacción:\xa0\n06/07/2026\n"
    "CUS:\xa0455692497\n"
    "Gracias\xa0por\xa0utilizar\xa0nuestro\xa0servicio.\n"
)


# --- parser: happy path (clean text) ---

def test_parsea_monto_pse() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PSE)
    assert resultado.monto == Decimal("124200.00")


def test_parsea_descripcion_contiene_empresa() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PSE)
    assert "WOMPI S.A.S" in resultado.descripcion


def test_parsea_banco_origen_pse() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PSE)
    assert resultado.banco_origen == "PSE"


def test_parsea_fecha_egreso_date() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PSE)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 7
    assert resultado.fecha_egreso.day == 6


def test_parsea_fecha_egreso_hora_cero() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PSE)
    assert resultado.fecha_egreso.hour == 0
    assert resultado.fecha_egreso.minute == 0


# --- parser: NBSP variant ---

def test_parsea_monto_pse_nbsp() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PSE_NBSP)
    assert resultado.monto == Decimal("124200.00")


def test_parsea_empresa_nbsp() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PSE_NBSP)
    assert "WOMPI S.A.S" in resultado.descripcion


def test_parsea_fecha_nbsp() -> None:
    resultado = _PARSER.parsear("", _TEXTO_PSE_NBSP)
    assert resultado.fecha_egreso.day == 6
    assert resultado.fecha_egreso.month == 7
    assert resultado.fecha_egreso.year == 2026


# --- parser: error path ---

def test_sin_patron_lanza_error() -> None:
    with pytest.raises(ErrorParseoBanco, match="No se encontro patron"):
        _PARSER.parsear("", "Notificacion irrelevante sin datos PSE")


# --- detectar_banco ---

def test_detectar_banco_cuerpo_pse_retorna_pse() -> None:
    assert detectar_banco("agenciagaraytour1@gmail.com", _TEXTO_PSE) == "PSE"


def test_detectar_banco_cuerpo_pse_con_nequi_retorna_pse() -> None:
    """PSE takes precedence even when body also mentions Nequi."""
    cuerpo_con_nequi = _TEXTO_PSE + "\nNequi cobró una comisión."
    assert detectar_banco("agenciagaraytour1@gmail.com", cuerpo_con_nequi) == "PSE"


def test_detectar_direccion_pse_retorna_egreso() -> None:
    assert detectar_direccion(_TEXTO_PSE) == "egreso"


# --- fabrica ---

def test_obtener_parser_egreso_pse_retorna_instancia() -> None:
    parser = obtener_parser_egreso("PSE")
    assert isinstance(parser, ParserPSEEgreso)
