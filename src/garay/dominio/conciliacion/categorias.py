"""Category constants for expense classification.

Single source of truth for expense category identifiers.
No imports from infraestructura/ or aplicacion/.
"""

from __future__ import annotations

from typing import Final

CATEGORIA_TRANSPORTE: Final[str] = "transporte"
CATEGORIA_OTRO: Final[str] = "otro"

_BANCOS_TRANSPORTE: frozenset[str] = frozenset(["Uber", "DiDi"])


def banco_a_categoria(banco: str) -> str:
    """Return the expense category for a given bank identifier.

    Returns CATEGORIA_TRANSPORTE for Uber and DiDi.
    Returns CATEGORIA_OTRO for all other banks.
    """
    if banco in _BANCOS_TRANSPORTE:
        return CATEGORIA_TRANSPORTE
    return CATEGORIA_OTRO
