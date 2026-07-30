"""Tests for ParserBancolombia — TDD RED phase."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.infraestructura.webhook.parser.bancolombia import ParserBancolombia
from garay.infraestructura.webhook.parser.base import ErrorParseoBanco

_PARSER = ParserBancolombia()

# Bancolombia-to-Bancolombia format
_TEXTO_BC_A_BC = (
    "Recibiste una transferencia por $1,500,000 de Juan Perez "
    "en tu cuenta **5643, el 15/07/26 a las 10:30"
)

_TEXTO_BC_A_BC_4_DIGITOS = (
    "Recibiste una transferencia por $250,000.50 de Maria Lopez "
    "en tu cuenta **1234, el 29/04/2026 a las 04:27"
)

# External bank to Bancolombia format
_TEXTO_EXTERNO = (
    "recibiste una transferencia de Carlos Gomez por $500,000 "
    "el 15/07/26 a las 10:30"
)

# Provider/gateway payment format (e.g. Wompi payment link) — real forwarded email
_TEXTO_PAGO_PROVEEDOR = (
    "Bancolombia: Recibiste un pago PROVEEDOR de WOMPI S.A.S. por $208,929.30 "
    "en tu cuenta de Ahorros el 30/07/2026 a las 12:06. Si tienes dudas, "
    "llamanos al 018000931987. A tu lado siempre."
)


def test_bc_a_bc_parsea_remitente_y_monto() -> None:
    resultado = _PARSER.parsear(_TEXTO_BC_A_BC, _TEXTO_BC_A_BC)

    assert resultado.remitente == "Juan Perez"
    assert resultado.monto == Decimal("1500000")
    assert resultado.banco_origen == "Bancolombia"


def test_bc_a_bc_parsea_fecha_2_digitos_anio() -> None:
    resultado = _PARSER.parsear(_TEXTO_BC_A_BC, _TEXTO_BC_A_BC)

    assert resultado.fecha_pago.year == 2026
    assert resultado.fecha_pago.month == 7
    assert resultado.fecha_pago.day == 15
    assert resultado.fecha_pago.hour == 10
    assert resultado.fecha_pago.minute == 30


def test_bc_a_bc_parsea_fecha_4_digitos_anio() -> None:
    resultado = _PARSER.parsear(_TEXTO_BC_A_BC_4_DIGITOS, _TEXTO_BC_A_BC_4_DIGITOS)

    assert resultado.fecha_pago.year == 2026
    assert resultado.fecha_pago.month == 4
    assert resultado.fecha_pago.day == 29
    assert resultado.monto == Decimal("250000.50")


def test_bc_a_bc_usa_cuerpo_html_si_texto_vacio() -> None:
    html = "<p>Recibiste una transferencia por $500,000 de Carlos Rios en tu cuenta **9999, el 01/01/26 a las 09:00</p>"  # noqa: E501
    resultado = _PARSER.parsear(html, "")

    assert resultado.remitente == "Carlos Rios"
    assert resultado.monto == Decimal("500000")


def test_externo_parsea_remitente_y_monto() -> None:
    resultado = _PARSER.parsear(_TEXTO_EXTERNO, _TEXTO_EXTERNO)

    assert resultado.remitente == "Carlos Gomez"
    assert resultado.monto == Decimal("500000")
    assert resultado.banco_origen == "Bancolombia"


def test_pago_proveedor_parsea_remitente_y_monto() -> None:
    resultado = _PARSER.parsear(_TEXTO_PAGO_PROVEEDOR, _TEXTO_PAGO_PROVEEDOR)

    assert resultado.remitente == "WOMPI S.A.S."
    assert resultado.monto == Decimal("208929.30")
    assert resultado.banco_origen == "Bancolombia"


def test_pago_proveedor_parsea_fecha_y_hora() -> None:
    resultado = _PARSER.parsear(_TEXTO_PAGO_PROVEEDOR, _TEXTO_PAGO_PROVEEDOR)

    assert resultado.fecha_pago.year == 2026
    assert resultado.fecha_pago.month == 7
    assert resultado.fecha_pago.day == 30
    assert resultado.fecha_pago.hour == 12
    assert resultado.fecha_pago.minute == 6


def test_texto_sin_patron_lanza_error_parseo() -> None:
    with pytest.raises(ErrorParseoBanco, match="No se encontro patron"):
        _PARSER.parsear("Notificacion irrelevante", "Notificacion irrelevante")


def test_monto_invalido_bc_a_bc_lanza_error() -> None:
    texto = "Recibiste una transferencia por $ABC de Ana en tu cuenta **1111, el 01/01/26 a las 09:00"  # noqa: E501
    with pytest.raises(ErrorParseoBanco):
        _PARSER.parsear(texto, texto)
