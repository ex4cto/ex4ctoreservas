"""Canonical parser for Colombian peso amounts entered by users.

Accepts full notation ('500000', '500.000') and miles shorthand ('500' → 500,000).
Plain numbers < 1000 are treated as miles de pesos (Colombian everyday convention),
so a tour priced at 300,000 can be typed simply as '300'.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def parsear_monto(texto: str) -> Decimal | None:
    """Parse a Colombian peso amount string.

    Returns a non-negative ``Decimal`` (scaling plain numbers < 1000 by x1000),
    or ``None`` when the text is empty, negative or non-numeric.
    """
    limpio = texto.strip().replace(".", "").replace(",", "")
    try:
        valor = Decimal(limpio)
    except InvalidOperation:
        return None
    if valor < Decimal("0"):
        return None
    if Decimal("0") < valor < Decimal("1000"):
        valor = valor * 1000
    return valor
