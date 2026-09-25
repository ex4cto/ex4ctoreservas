"""Application-layer errors for the ventas module."""

from __future__ import annotations

from garay.dominio.comun.errores import ErrorDeDominio


class ServicioMultipleNoSoportado(ErrorDeDominio):
    """MVP: editar tour solo soporta ventas con un único servicio."""


class ServicioNoEncontrado(ErrorDeDominio):
    """No se encontró el servicio con el ID indicado o no está activo."""


class ServicioSinPrecio(ErrorDeDominio):
    """El servicio no tiene precio_neto_adulto registrado en el catálogo."""
