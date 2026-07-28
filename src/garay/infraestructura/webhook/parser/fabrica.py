"""Factory for bank parsers."""

from __future__ import annotations

from garay.infraestructura.webhook.parser.bancolombia import ParserBancolombia
from garay.infraestructura.webhook.parser.base import (
    BANCO_BANCOLOMBIA,
    BANCO_NEQUI,
    ErrorParseoBanco,
    ParserBanco,
)
from garay.infraestructura.webhook.parser.nequi import ParserNequi

_PARSERS: dict[str, ParserBanco] = {
    BANCO_BANCOLOMBIA: ParserBancolombia(),
    BANCO_NEQUI: ParserNequi(),
}


def obtener_parser(banco: str) -> ParserBanco:
    """Return the parser for the given bank name.

    Raises ErrorParseoBanco if the bank is not supported.
    """
    if banco not in _PARSERS:
        raise ErrorParseoBanco(f"Banco no soportado: '{banco}'")
    return _PARSERS[banco]
