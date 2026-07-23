from __future__ import annotations

from garay.dominio.comun.errores import ErrorDeDominio


class MontoInvalido(ErrorDeDominio):
    """El monto debe ser mayor que cero."""


class DescripcionEgresoVacia(ErrorDeDominio):
    """La descripcion del egreso no puede estar vacia."""


class ReferenciaIngresoVacia(ErrorDeDominio):
    """La referencia del ingreso no puede estar vacia."""
