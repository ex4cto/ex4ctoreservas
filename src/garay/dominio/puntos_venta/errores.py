"""Errores de dominio del modulo puntos de venta."""

from __future__ import annotations

from garay.dominio.comun.errores import ErrorDeDominio


class PorcentajeCapaInvalido(ErrorDeDominio):
    """El porcentaje de capa debe ser mayor que 0 y no puede superar 100."""


class NombrePuntoVacio(ErrorDeDominio):
    """El nombre del punto de venta no puede estar vacio."""
