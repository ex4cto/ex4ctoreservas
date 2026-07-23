"""Errores de dominio del modulo freelancers."""

from __future__ import annotations

from garay.dominio.comun.errores import ErrorDeDominio


class NombreFreelancerVacio(ErrorDeDominio):
    """El nombre del freelancer no puede estar vacio."""
