"""Domain port: GeneradorListaPreciosPort.

Pure abstract port — zero infrastructure imports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from garay.dominio.servicios.entidades import Servicio, TipoImagen


class GeneradorListaPreciosPort(ABC):
    """Generates a price-list image for a given audience type.

    Returns raw PNG bytes. Concrete implementations (e.g. Playwright+Jinja2)
    live in the infrastructure layer.
    """

    @abstractmethod
    async def generar_imagen_precios(
        self,
        servicios: list[Servicio],
        tipo: TipoImagen,
    ) -> bytes:
        """Render a price-list image and return it as PNG bytes."""
        ...
