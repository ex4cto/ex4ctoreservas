"""Factory for bank parsers."""

from __future__ import annotations

from garay.infraestructura.webhook.parser.bancolombia import ParserBancolombia
from garay.infraestructura.webhook.parser.bancolombia_egreso import ParserBancolombiaEgreso
from garay.infraestructura.webhook.parser.base import (
    BANCO_BANCOLOMBIA,
    BANCO_NEQUI,
    ErrorParseoBanco,
    ParserBanco,
    ParserEgreso,
)
from garay.infraestructura.webhook.parser.nequi import ParserNequi
from garay.infraestructura.webhook.parser.nequi_egreso import ParserNequiEgreso

_PARSERS: dict[str, ParserBanco] = {
    BANCO_BANCOLOMBIA: ParserBancolombia(),
    BANCO_NEQUI: ParserNequi(),
}

_PARSERS_EGRESO: dict[str, ParserEgreso] = {
    BANCO_BANCOLOMBIA: ParserBancolombiaEgreso(),
    BANCO_NEQUI: ParserNequiEgreso(),
}


def obtener_parser(banco: str) -> ParserBanco:
    """Return the ingreso parser for the given bank name.

    Raises ErrorParseoBanco if the bank is not supported.
    """
    if banco not in _PARSERS:
        raise ErrorParseoBanco(f"Banco no soportado: '{banco}'")
    return _PARSERS[banco]


def obtener_parser_egreso(banco: str) -> ParserEgreso:
    """Return the egreso parser for the given bank name.

    Raises ErrorParseoBanco if the bank is not supported.
    """
    if banco not in _PARSERS_EGRESO:
        raise ErrorParseoBanco(f"Banco no soportado para egresos: '{banco}'")
    return _PARSERS_EGRESO[banco]
