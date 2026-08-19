"""Tests for ParserNequiEgreso — RED phase."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.infraestructura.webhook.parser.base import ErrorParseoBanco
from garay.infraestructura.webhook.parser.nequi_egreso import ParserNequiEgreso

_PARSER = ParserNequiEgreso()

_TEXTO_ENVIO_1 = (
    "Enviaste de manera exitosa 5.000 a la llave 1047487553 de BRYAN CASTRO "
    "el 25 de julio de 2026 a las 7:05 p.m."
)
_TEXTO_ENVIO_2 = (
    "Enviaste de manera exitosa 100 a la llave 1047487553 de BRYAN CASTRO "
    "el 22 de junio de 2026 a las 4:59 p.m."
)
_TEXTO_FACTURA_1 = (
    "Pagaste con Nequi tu factura por $3.000\n"
    "Nombre: Daniela Romero\n"
    "Fecha: 25/Jul/2026\n"
    "Valor: $3.000"
)
_TEXTO_FACTURA_2 = (
    "Pagaste con Nequi tu factura por $9.000\n"
    "Fecha: 21/Jul/2026\n"
    "Valor: $9.000"
)


# --- tipo 1: envio Bre-B ---

def test_parsea_envio_monto_con_punto_miles() -> None:
    resultado = _PARSER.parsear("", _TEXTO_ENVIO_1)
    assert resultado.monto == Decimal("5000")


def test_parsea_envio_descripcion() -> None:
    resultado = _PARSER.parsear("", _TEXTO_ENVIO_1)
    assert resultado.descripcion == "Envio a BRYAN CASTRO"


def test_parsea_envio_banco_origen() -> None:
    resultado = _PARSER.parsear("", _TEXTO_ENVIO_1)
    assert resultado.banco_origen == "Nequi"


def test_parsea_envio_fecha() -> None:
    resultado = _PARSER.parsear("", _TEXTO_ENVIO_1)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 7
    assert resultado.fecha_egreso.day == 25
    assert resultado.fecha_egreso.hour == 19
    assert resultado.fecha_egreso.minute == 5


def test_parsea_envio_monto_numero_plano() -> None:
    resultado = _PARSER.parsear("", _TEXTO_ENVIO_2)
    assert resultado.monto == Decimal("100")


def test_parsea_envio_fecha_junio() -> None:
    resultado = _PARSER.parsear("", _TEXTO_ENVIO_2)
    assert resultado.fecha_egreso.month == 6
    assert resultado.fecha_egreso.day == 22


# --- tipo 2: pago factura ---

def test_parsea_factura_monto() -> None:
    resultado = _PARSER.parsear("", _TEXTO_FACTURA_1)
    assert resultado.monto == Decimal("3000")


def test_parsea_factura_descripcion() -> None:
    resultado = _PARSER.parsear("", _TEXTO_FACTURA_1)
    assert resultado.descripcion == "Pago factura Nequi"


def test_parsea_factura_fecha() -> None:
    resultado = _PARSER.parsear("", _TEXTO_FACTURA_1)
    assert resultado.fecha_egreso.year == 2026
    assert resultado.fecha_egreso.month == 7
    assert resultado.fecha_egreso.day == 25


def test_parsea_factura_9000() -> None:
    resultado = _PARSER.parsear("", _TEXTO_FACTURA_2)
    assert resultado.monto == Decimal("9000")
    assert resultado.fecha_egreso.day == 21


# --- error ---

def test_texto_sin_patron_lanza_error() -> None:
    with pytest.raises(ErrorParseoBanco, match="No se encontro patron"):
        _PARSER.parsear("", "Mensaje Nequi sin datos de egreso")


# --- tipo 3: pago a comercio ---

def test_parsear_pago_comercio_nequi() -> None:
    cuerpo = (
        "¡Pago exitoso!\n"
        "Hiciste un pago en Kushki Colombia SA por $100.000\n"
        "Fecha: El 13 de junio de 2026\n"
        "Hora: 4:46 p. m.\n"
        "CUS: 389067474"
    )
    resultado = _PARSER.parsear("", cuerpo)
    assert resultado.monto == Decimal("100000")
    assert resultado.descripcion == "Pago en Kushki Colombia SA"
    assert resultado.fecha_egreso.date() == datetime.date(2026, 6, 13)
    assert resultado.fecha_egreso.hour == 16
    assert resultado.fecha_egreso.minute == 46


def test_parsear_pago_comercio_hora_am() -> None:
    cuerpo = (
        "Hiciste un pago en Claro por $9.000\n"
        "Fecha: El 21 de julio de 2026\n"
        "Hora: 10:30 a. m.\n"
    )
    resultado = _PARSER.parsear("", cuerpo)
    assert resultado.fecha_egreso.hour == 10
    assert resultado.monto == Decimal("9000")


def test_parsear_pago_comercio_hora_12pm() -> None:
    cuerpo = (
        "Hiciste un pago en Netflix por $17.900\n"
        "Fecha: El 1 de marzo de 2026\n"
        "Hora: 12:00 p. m.\n"
    )
    resultado = _PARSER.parsear("", cuerpo)
    assert resultado.fecha_egreso.hour == 12


def test_parsear_pago_comercio_nombre_largo() -> None:
    cuerpo = (
        "Hiciste un pago en Movistar Colombia S.A. por $50.000\n"
        "Fecha: El 5 de agosto de 2026\n"
        "Hora: 3:15 p. m.\n"
    )
    resultado = _PARSER.parsear("", cuerpo)
    assert resultado.descripcion == "Pago en Movistar Colombia S.A."
    assert resultado.monto == Decimal("50000")


def test_parsea_envio_a_la_una_en_punto() -> None:
    """1 o'clock reads 'a la 1:15' (singular), not 'a las' — must still parse."""
    cuerpo = (
        "Enviaste de manera exitosa 59.000 a la llave 0091963837 de FAVIPAN CRESPO "
        "el 11 de julio de 2026 a la 1:15 a.m."
    )
    resultado = _PARSER.parsear("", cuerpo)
    assert resultado.monto == Decimal("59000")
    assert resultado.descripcion == "Envio a FAVIPAN CRESPO"
    assert resultado.fecha_egreso.hour == 1


def test_parsea_envio_con_nbsp_y_saltos() -> None:
    """Forwarded emails carry NBSP (\\xa0) and line breaks; must still parse."""
    cuerpo = (
        "Enviaste de manera exitosa\xa0300.000 a la llave 0092631303 de GRAFHIC\n"
        "DESIGN G D el 10 de julio de 2026 a las\xa012:29 p.m."
    )
    resultado = _PARSER.parsear("", cuerpo)
    assert resultado.monto == Decimal("300000")
    assert resultado.descripcion == "Envio a GRAFHIC DESIGN G D"


def test_parsea_envio_llave_con_arroba() -> None:
    """Bre-B keys can be @user (not only digits) — must still parse."""
    cuerpo = (
        "Enviaste de manera exitosa 10.000 a la llave @9019221257 de NEW DAYS HOSTELS SAS "
        "el 13 de julio de 2026 a las 11:47 a.m."
    )
    resultado = _PARSER.parsear("", cuerpo)
    assert resultado.monto == Decimal("10000")
    assert resultado.descripcion == "Envio a NEW DAYS HOSTELS SAS"


# --- destinatario wiring (REQ-1) ---

class TestNequiDestinatario:
    """EgresoExtraido.destinatario is populated from the correct Nequi regex group."""

    def test_envio_breb_produce_nombre_como_destinatario(self) -> None:
        resultado = _PARSER.parsear("", _TEXTO_ENVIO_1)
        assert resultado.destinatario == "BRYAN CASTRO"

    def test_pago_comercio_produce_nombre_como_destinatario(self) -> None:
        cuerpo = (
            "¡Pago exitoso!\n"
            "Hiciste un pago en Rappi por $50.000\n"
            "Fecha: El 5 de agosto de 2026\n"
            "Hora: 3:15 p. m.\n"
        )
        resultado = _PARSER.parsear("", cuerpo)
        assert resultado.destinatario == "Rappi"

    def test_pago_factura_produce_none(self) -> None:
        """'Pago factura Nequi' has no recipient — destinatario must be None."""
        resultado = _PARSER.parsear("", _TEXTO_FACTURA_1)
        assert resultado.destinatario is None

    def test_envio_con_utf8_nombre(self) -> None:
        """UTF-8 special characters in name must survive without encoding loss."""
        cuerpo = (
            "Enviaste de manera exitosa 10.000 a la llave 3011234567 de "
            "José María Ñoño el 1 de agosto de 2026 a las 10:00 a.m."
        )
        resultado = _PARSER.parsear("", cuerpo)
        assert resultado.destinatario == "José María Ñoño"


# --- parser-layer empty-recipient guard — structural analysis (REQ-1, REQ-5) ---
#
# ParserNequiEgreso applies re.sub(r"\s+", " ", ...) before any regex match.
# This normalization collapses all consecutive whitespace (including \xa0, \n)
# to a single space, making it structurally impossible for (.+?) groups to
# capture a whitespace-only string after .strip():
#
#   _PATRON_ENVIO (.+? between '\s+de\s+' and '\s+el\s+'):
#     "de   el" normalizes to "de el"; \s+de\s+ consumes " de ", (.+?) would
#     need to match before "\s+el" but the next text is "el" with no preceding
#     space — no match. Whitespace-only capture impossible.
#
#   _PATRON_PAGO_COMERCIO (.+? between 'en ' and ' por $'):
#     "en   por" normalizes to "en por"; \s+de\s+ variant consumes space,
#     (.+?) captures "p" of "por" — not whitespace-only.
#
#   _PATRON_FACTURA: no recipient extracted; destinatario is hardcoded None.
#
# Conclusion: no parser-layer empty-recipient test is needed or meaningful for
# Nequi. The 'nombre or None' / 'comercio or None' guards exist for defensive
# correctness; their trigger condition cannot arise from a real regex match after
# whitespace normalization.
#
# The domain entity guard (ValueError on empty/whitespace string) remains the
# authoritative last line of defense and is covered in test_egreso.py.
