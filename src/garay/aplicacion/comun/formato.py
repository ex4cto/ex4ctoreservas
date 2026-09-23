"""Shared money formatting utilities for display."""

from __future__ import annotations

from decimal import Decimal

from garay.dominio.comun.dinero import Dinero


def fmt_cop(valor: Dinero | Decimal | None) -> str:
    """Format a COP monetary value as $N.NNN (Colombian dot-thousands notation).

    Accepts Dinero, Decimal, or None (returns '—' for None).
    """
    if valor is None:
        return "—"
    monto = valor.monto if isinstance(valor, Dinero) else valor
    return "$" + f"{int(monto):,}".replace(",", ".")
