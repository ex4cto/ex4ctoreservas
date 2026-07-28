"""Tests for fabrica de parsers — TDD RED phase."""

from __future__ import annotations

import pytest

from garay.infraestructura.webhook.parser.bancolombia import ParserBancolombia
from garay.infraestructura.webhook.parser.base import ErrorParseoBanco
from garay.infraestructura.webhook.parser.fabrica import obtener_parser
from garay.infraestructura.webhook.parser.nequi import ParserNequi


def test_obtener_parser_bancolombia() -> None:
    parser = obtener_parser("Bancolombia")
    assert isinstance(parser, ParserBancolombia)


def test_obtener_parser_nequi() -> None:
    parser = obtener_parser("Nequi")
    assert isinstance(parser, ParserNequi)


def test_banco_no_soportado_lanza_error() -> None:
    with pytest.raises(ErrorParseoBanco, match="Banco no soportado"):
        obtener_parser("DaviPlata")
