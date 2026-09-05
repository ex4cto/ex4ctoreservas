"""GenerarPropuestaAudiovisualService — fills the audiovisual proposal template.

Variables de la propuesta audiovisual: nombre de la empresa y precios (planes +
complementos). El servicio es puro — recibe la plantilla y el logo como strings
(sin IO), como GenerarFacturaService recibe la URL del logo. La carga de la
plantilla y el base64 del logo ocurren en el wiring (main.py).
"""

from __future__ import annotations

from garay.aplicacion.propuestas.formato import formatear_cop
from garay.dominio.propuestas.contexto import PropuestaContexto

_PH_EMPRESA = "{{EMPRESA}}"
_PH_LOGO = "{{LOGO}}"
_PH_PRECIO_COMPLETO = "{{PRECIO_COMPLETO}}"
_PH_PRECIO_MEDIO = "{{PRECIO_MEDIO}}"
_PH_PRECIO_COMMUNITY = "{{PRECIO_COMMUNITY}}"
_PH_PRECIO_TRAFFICKER = "{{PRECIO_TRAFFICKER}}"


class GenerarPropuestaAudiovisualService:
    """Render the audiovisual proposal HTML for a given company."""

    def __init__(self, plantilla: str, logo_data_uri: str = "") -> None:
        self._plantilla = plantilla
        self._logo_data_uri = logo_data_uri

    def generar(self, ctx: PropuestaContexto) -> str:
        """Return the proposal HTML with the company name, logo and prices filled in."""
        precios = ctx.precios
        return (
            self._plantilla.replace(_PH_EMPRESA, ctx.empresa_nombre)
            .replace(_PH_LOGO, self._logo_data_uri)
            .replace(_PH_PRECIO_COMPLETO, formatear_cop(precios.completo.monto))
            .replace(_PH_PRECIO_MEDIO, formatear_cop(precios.medio.monto))
            .replace(_PH_PRECIO_COMMUNITY, formatear_cop(precios.community.monto))
            .replace(_PH_PRECIO_TRAFFICKER, formatear_cop(precios.trafficker.monto))
        )
