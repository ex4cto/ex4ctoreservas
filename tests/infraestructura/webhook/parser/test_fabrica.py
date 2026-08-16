"""Tests for fabrica de parsers — TDD RED phase."""

from __future__ import annotations

import pytest

from garay.infraestructura.webhook.parser.bancolombia import ParserBancolombia
from garay.infraestructura.webhook.parser.base import BANCO_DIDI, BANCO_UBER, ErrorParseoBanco
from garay.infraestructura.webhook.parser.didi_egreso import ParserDiDiEgreso
from garay.infraestructura.webhook.parser.fabrica import obtener_parser, obtener_parser_egreso
from garay.infraestructura.webhook.parser.nequi import ParserNequi
from garay.infraestructura.webhook.parser.uber_egreso import ParserUberEgreso


def test_obtener_parser_bancolombia() -> None:
    parser = obtener_parser("Bancolombia")
    assert isinstance(parser, ParserBancolombia)


def test_obtener_parser_nequi() -> None:
    parser = obtener_parser("Nequi")
    assert isinstance(parser, ParserNequi)


def test_banco_no_soportado_lanza_error() -> None:
    with pytest.raises(ErrorParseoBanco, match="Banco no soportado"):
        obtener_parser("DaviPlata")


def test_obtener_parser_egreso_uber() -> None:
    parser = obtener_parser_egreso(BANCO_UBER)
    assert isinstance(parser, ParserUberEgreso)


def test_obtener_parser_egreso_didi() -> None:
    parser = obtener_parser_egreso(BANCO_DIDI)
    assert isinstance(parser, ParserDiDiEgreso)


def test_banco_egreso_no_soportado_lanza_error() -> None:
    with pytest.raises(ErrorParseoBanco, match="Banco no soportado"):
        obtener_parser_egreso("DaviPlata")
