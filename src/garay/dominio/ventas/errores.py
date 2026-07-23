"""Errores de dominio del modulo ventas."""

from __future__ import annotations

from garay.dominio.comun.dinero import MonedaIncompatible as MonedaIncompatible  # re-export
from garay.dominio.comun.errores import ErrorDeDominio


class GananciaNegativa(ErrorDeDominio):
    """El neto supera al valor de venta, lo que produciria una ganancia negativa."""


class ValorVentaInvalido(ErrorDeDominio):
    """El valor de venta debe ser mayor que cero."""
