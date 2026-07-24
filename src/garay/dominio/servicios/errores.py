"""Errores de dominio del modulo servicios."""

from __future__ import annotations

from garay.dominio.comun.errores import ErrorDeDominio


class NombreServicioVacio(ErrorDeDominio):
    """El nombre del servicio no puede estar vacio."""


class NumeroServicioInvalido(ErrorDeDominio):
    """El numero del servicio debe ser mayor a cero."""
