from __future__ import annotations

from garay.dominio.comun.errores import ErrorDeDominio


class PorcentajeInvalidoRegla(ErrorDeDominio):
    """Un porcentaje de la regla de comision es invalido."""


class PorcentajeReferidoSuperaTecho(ErrorDeDominio):
    """El porcentaje de referido supera el maximo permitido por la regla."""


class ReglasNoEncontradas(ErrorDeDominio):
    """No se encontraron reglas de comision para el tipo de cliente indicado."""
