"""GenerarPropuestaAudiovisualService — fills the audiovisual proposal template.

MVP (walking skeleton): the only variable is the company name. The service is
pure — it receives the template and logo as strings (no IO) so it stays trivially
testable, mirroring GenerarFacturaService which receives the logo URL in its
constructor. Template loading and logo base64 encoding happen at wiring time.
"""

from __future__ import annotations

_PH_EMPRESA = "{{EMPRESA}}"
_PH_LOGO = "{{LOGO}}"


class GenerarPropuestaAudiovisualService:
    """Render the audiovisual proposal HTML for a given company."""

    def __init__(self, plantilla: str, logo_data_uri: str = "") -> None:
        self._plantilla = plantilla
        self._logo_data_uri = logo_data_uri

    def generar(self, empresa_nombre: str) -> str:
        """Return the proposal HTML with the company name and logo filled in."""
        return self._plantilla.replace(_PH_EMPRESA, empresa_nombre).replace(
            _PH_LOGO, self._logo_data_uri
        )
