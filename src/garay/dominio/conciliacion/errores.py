from __future__ import annotations

from garay.dominio.comun.errores import ErrorDeDominio


class MontoInvalido(ErrorDeDominio):
    """El monto debe ser mayor que cero."""


class DescripcionEgresoVacia(ErrorDeDominio):
    """La descripcion del egreso no puede estar vacia."""


class ReferenciaIngresoVacia(ErrorDeDominio):
    """La referencia del ingreso no puede estar vacia."""


class CategoriaEgresoDuplicada(ErrorDeDominio):
    """Ya existe una categoria de egreso con ese nombre."""


class CategoriaEgresoProtegida(ErrorDeDominio):
    """La categoria de egreso esta protegida y no puede desactivarse ni renombrarse."""


class EgresoNoEditable(ErrorDeDominio):
    """Solo los egresos manuales se pueden editar (los automaticos no)."""
