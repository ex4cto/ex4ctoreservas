"""Errores de dominio del modulo servicios."""

from __future__ import annotations

from garay.dominio.comun.errores import ErrorDeDominio


class NombreServicioVacio(ErrorDeDominio):
    """El nombre del servicio no puede estar vacio."""


class NumeroServicioInvalido(ErrorDeDominio):
    """El numero del servicio debe ser mayor a cero."""


class HorarioInvalido(ErrorDeDominio):
    """The time value is not a valid time or has an unrecognized format."""


class HorarioDuplicado(ErrorDeDominio):
    """The canonical time already exists in the schedule list for this tour."""
