"""Tests for ParserBancolombiaEgreso — RED phase."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.infraestructura.webhook.parser.bancolombia_egreso import (
    ParserBancolombiaEgreso,
    _parsear_monto_bilingue,
)
from garay.infraestructura.webhook.parser.base import ErrorParseoBanco
from garay.infraestructura.webhook.schemas import EgresoExtraido

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


# --- single-digit hour / day ---

def test_compra_hora_un_digito() -> None:
    texto = (
        "Bancolombia: Compraste $10.000,00 en GAZEL EL TIGRE con tu T.Deb *9283, "
        "el 12/07/2026 a las 9:43."
    )
    resultado = _PARSER.parsear("", texto)
    assert resultado.fecha_egreso.hour == 9
    assert resultado.fecha_egreso.minute == 43


def test_transferencia_breb_dia_un_digito() -> None:
    texto = (
        "Bancolombia: BRYAN, transferiste $6,000.00 a la llave 3015879983 desde tu cuenta *7488 "
        "a NEIDA GARCIA el 5/07/26 a las 16:26."
    )
    resultado = _PARSER.parsear("", texto)
    assert resultado.fecha_egreso.day == 5
    assert resultado.monto == Decimal("6000.00")


# --- spaced-account destination (prod bug regression) ---

def test_transferencia_cuenta_destino_con_espacio_tras_asterisco() -> None:
    """Account destination '* 08600002475' (space after *) must parse correctly.

    Real failing email body from prod quarantine on 2026-08-10.
    """
    texto = (
        "Transferiste $580,000 desde tu cuenta *5643 a la cuenta * 08600002475 "
        "el 10/08/2026 a las 10:55."
    )
    resultado = _PARSER.parsear("", texto)
    assert resultado.monto == Decimal("580000")
    assert resultado.fecha_egreso.date().isoformat() == "2026-08-10"
    assert "08600002475" in resultado.descripcion


# --- destinatario wiring (REQ-1, REQ-5) ---

class TestBancolombiaDestinatario:
    """EgresoExtraido.destinatario is populated from the correct regex group."""

    def test_breb_produce_nombre_como_destinatario(self) -> None:
        resultado = _PARSER.parsear("", _TEXTO_TRANSFERENCIA_BREB)
        assert resultado.destinatario == "NEIDA GARCIA"

    def test_compra_produce_comercio_como_destinatario(self) -> None:
        resultado = _PARSER.parsear("", _TEXTO_COMPRA)
        assert resultado.destinatario == "MOVISTAR PAGOSEPAYCO"

    def test_transferencia_cuenta_produce_mascara(self) -> None:
        resultado = _PARSER.parsear("", _TEXTO_TRANSFERENCIA_CUENTA)
        assert resultado.destinatario == "*3207904880"

    def test_transferencia_cuenta_con_espacio_produce_mascara(self) -> None:
        texto = (
            "Transferiste $580,000 desde tu cuenta *5643 a la cuenta * 08600002475 "
            "el 10/08/2026 a las 10:55."
        )
        resultado = _PARSER.parsear("", texto)
        assert resultado.destinatario == "*08600002475"

    def test_destinatario_nunca_es_cadena_vacia(self) -> None:
        """EgresoExtraido.destinatario must never be '' — guard returns None (REQ-5)."""
        # Construct a fake EgresoExtraido directly to verify the schema default
        eo = EgresoExtraido(
            monto=Decimal("1000"),
            descripcion="Test",
            banco_origen="Bancolombia",
            fecha_egreso=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        assert eo.destinatario is None


# --- parser-layer empty-recipient guard (REQ-1, REQ-5) ---
#
# _PATRON_TRANSFERENCIA_CUENTA uses ([\d]+) — digits only, cannot ever capture
# whitespace. The `cuenta or None` guard is structurally unreachable for that
# sub-type; no test is needed or possible for it.
#
# _PATRON_TRANSFERENCIA_BREB and _PATRON_COMPRA use (.+?) which CAN capture
# a single-space group when extra whitespace is present between the anchor
# keyword and the trailing delimiter. Bancolombia does NOT normalize whitespace
# before matching, so such bodies reach the regex unchanged.

class TestBancolombiaEmptyRecipientGuard:
    """Parser-layer `or None` guard yields None when regex group strips to '' (REQ-1, REQ-5)."""

    def test_breb_nombre_solo_espacios_produce_destinatario_none(self) -> None:
        """Bre-B body where the name slot contains only whitespace strips to '' → None."""
        # The name is a single space between 'a ' and ' el'. After strip() → ''.
        # 'nombre or None' must return None, and the parse must not raise.
        texto = (
            "Bancolombia: transferiste $6,000.00 a la llave 3015879983 desde tu cuenta "
            "*7488 a   el 25/07/26 a las 16:26."
        )
        resultado = _PARSER.parsear("", texto)
        assert resultado.destinatario is None

    def test_compra_comercio_solo_espacios_produce_destinatario_none(self) -> None:
        """Compra body where the merchant slot has only whitespace strips to '' → None."""
        # Extra spaces between 'en ' and ' con tu T.Deb'. After strip() → ''.
        # 'comercio or None' must return None, and the parse must not raise.
        texto = (
            "Bancolombia: Compraste $10.000,00 en   con tu T.Deb *9283, "
            "el 12/07/2026 a las 9:43."
        )
        resultado = _PARSER.parsear("", texto)
        assert resultado.destinatario is None
