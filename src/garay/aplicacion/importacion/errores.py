from __future__ import annotations


class ErrorImportacion(Exception):
    """Base de errores de la importacion de ventas historicas."""


class DescripcionSinMapeo(ErrorImportacion):
    """La descripcion del Excel no tiene un servicio mapeado en el alias."""
