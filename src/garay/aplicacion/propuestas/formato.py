"""Formateo de dinero para las plantillas de propuestas."""

from __future__ import annotations

from decimal import Decimal


def formatear_cop(monto: Decimal) -> str:
    """Format a Decimal as Colombian thousands: 3000000 -> '3.000.000' (no symbol)."""
    return f"{int(monto):,}".replace(",", ".")
