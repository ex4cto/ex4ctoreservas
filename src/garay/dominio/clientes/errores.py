"""Errores de dominio del modulo clientes."""

from __future__ import annotations

from garay.dominio.comun.errores import ErrorDeDominio


class NombreClienteVacio(ErrorDeDominio):
    """El nombre del cliente no puede ser vacio ni contener solo espacios."""
