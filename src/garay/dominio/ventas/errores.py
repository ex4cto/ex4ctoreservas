"""Errores de dominio del modulo ventas."""

from __future__ import annotations

from garay.dominio.comun.dinero import MonedaIncompatible as MonedaIncompatible  # re-export
from garay.dominio.comun.errores import ErrorDeDominio


class GananciaNegativa(ErrorDeDominio):
    """El neto supera al valor de venta, lo que produciria una ganancia negativa."""


class ValorVentaInvalido(ErrorDeDominio):
    """El valor de venta debe ser mayor que cero."""


class CantidadInvalida(ErrorDeDominio):
    """La cantidad de pasajeros debe ser al menos 1."""


class AbonoSuperaValorVenta(ErrorDeDominio):
    """El abono no puede superar el valor de la venta."""


class DigitalConPuntoDeVenta(ErrorDeDominio):
    """Una venta DIGITAL no puede tener un punto de venta asociado."""


class VentaYaAnulada(ErrorDeDominio):
    """No se puede anular una venta que ya fue anulada."""
