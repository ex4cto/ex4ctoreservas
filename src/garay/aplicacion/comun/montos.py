"""Canonical parser for Colombian peso amounts entered by users.

Accepted input formats:
  '500000'   → 500,000
  '500.000'  → 500,000  (Colombian thousands dot)
  '500'      → 500,000  (plain numbers < 1000 treated as miles de pesos)
  '500k'     → 500,000  (k/K suffix)
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def parsear_monto(texto: str) -> Decimal | None:
    """Parse a Colombian peso amount string.

    Returns a non-negative ``Decimal`` or ``None`` when the input is empty,
    negative, or non-numeric.
    """
    limpio = texto.strip()
    k_flag = limpio.lower().endswith("k")
    if k_flag:
        limpio = limpio[:-1]
    limpio = limpio.replace(".", "").replace(",", "")
    try:
        valor = Decimal(limpio)
    except InvalidOperation:
        return None
    if valor < Decimal("0"):
        return None
    if k_flag or Decimal("0") < valor < Decimal("1000"):
        valor = valor * 1000
    return valor
