"""GenerarPropuestaSoftwareService — fills the Ex4cto Reservas proposal template.

Variables: nombre de empresa, ejemplos de servicios del negocio (copy) y precios
de software. Dos precios son derivados de los base y se calculan aquí:
- equivalente mensual del plan anual = anual / 12 (redondeado)
- ahorro anual = mensual*12 - anual

Servicio puro (recibe plantilla y logo como strings, sin IO).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from garay.aplicacion.propuestas.formato import formatear_cop
from garay.dominio.propuestas.contexto import PropuestaContexto

_ENTERO = Decimal("1")


class GenerarPropuestaSoftwareService:
    """Render the software proposal HTML for a given company."""

    def __init__(self, plantilla: str, logo_data_uri: str = "") -> None:
        self._plantilla = plantilla
        self._logo_data_uri = logo_data_uri

    def generar(self, ctx: PropuestaContexto) -> str:
        """Return the proposal HTML with company, service examples and prices filled."""
        p = ctx.precios_software
        anual_mes = (p.anual.monto / 12).quantize(_ENTERO, rounding=ROUND_HALF_UP)
        ahorro = p.mensual.monto * 12 - p.anual.monto
        return (
            self._plantilla.replace("{{EMPRESA}}", ctx.empresa_nombre)
            .replace("{{LOGO}}", self._logo_data_uri)
            .replace("{{EJEMPLOS_SERVICIOS}}", ctx.ejemplos_servicios)
            .replace("{{PRECIO_DESARROLLO}}", formatear_cop(p.desarrollo.monto))
            .replace("{{PRECIO_IMPLEMENTACION}}", formatear_cop(p.implementacion.monto))
            .replace("{{PRECIO_MENSUAL}}", formatear_cop(p.mensual.monto))
            .replace("{{PRECIO_ANUAL}}", formatear_cop(p.anual.monto))
            .replace("{{PRECIO_ANUAL_MES}}", formatear_cop(anual_mes))
            .replace("{{PRECIO_AHORRO}}", formatear_cop(ahorro))
        )
