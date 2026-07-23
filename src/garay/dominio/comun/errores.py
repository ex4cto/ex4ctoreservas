"""Jerarquia de errores del sistema Garay."""


class ErrorGaray(Exception):
    """Raiz de todos los errores del sistema Garay."""


class ErrorDeDominio(ErrorGaray):
    """Se violo una regla o invariante del dominio."""


class ErrorDeConfiguracion(ErrorGaray):
    """Configuracion invalida o faltante."""
