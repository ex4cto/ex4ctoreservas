from __future__ import annotations

from garay.dominio.comun.errores import ErrorDeDominio


class TiqueteraYaProcesada(ErrorDeDominio):
    """Se intento procesar una tiquetera que ya fue procesada."""


class FotoReferenciaVacia(ErrorDeDominio):
    """La foto de referencia no puede estar vacia."""
