"""Application service: PublicarListaPreciosServicio.

Orchestrates image generation and distribution of the price list.
Uses asyncio.to_thread to bridge the sync ServicioRepository.
"""

from __future__ import annotations

import asyncio
import logging

from garay.dominio.puertos.generador_lista_precios import GeneradorListaPreciosPort
from garay.dominio.puertos.repositorios import ServicioRepository
from garay.dominio.puertos.servicios_externos import EnviadorFotoPort
from garay.dominio.servicios.entidades import Servicio, TipoImagen

logger = logging.getLogger(__name__)

# Module-level concurrency guard.  A plain bool flag is race-free within a
# single asyncio event loop and works correctly across separate asyncio.run()
# calls in scripts (each gets a fresh module state in the same process).
_generando: bool = False


class PublicarListaPreciosServicio:
    """Generates and distributes two price-list images (INTERNA + TURISTA).

    Constructor parameters:
        repo: sync ServicioRepository (bridged via asyncio.to_thread)
        generador: async port that renders PNG bytes
        enviador_foto: async port that sends PNG bytes to a Telegram group
        grupo_id: destination Telegram group ID (empty string = skip send)
    """

    def __init__(
        self,
        repo: ServicioRepository,
        generador: GeneradorListaPreciosPort,
        enviador_foto: EnviadorFotoPort,
        grupo_id: str,
    ) -> None:
        self._repo = repo
        self._generador = generador
        self._enviador_foto = enviador_foto
        self._grupo_id = grupo_id

    async def publicar(self) -> None:
        """Generate INTERNA + TURISTA images and send both to grupo_id.

        Steps:
            1. Fetch active services via asyncio.to_thread (sync repo).
            2. Filter: activo=True AND precio_sugerido_adulto is not None.
            3. Early return if filtered list is empty.
            4. Generate INTERNA image.
            5. Generate TURISTA image.
            6. If grupo_id non-empty, send both images.
        """
        servicios: list[Servicio] = await asyncio.to_thread(self._repo.listar_activos)

        filtrados = [
            s
            for s in servicios
            if s.activo
            and s.precio_neto_adulto is not None
            and s.precio_sugerido_adulto is not None
        ]

        if not filtrados:
            return

        img_interna = await self._generador.generar_imagen_precios(
            filtrados, TipoImagen.INTERNA
        )
        img_turista = await self._generador.generar_imagen_precios(
            filtrados, TipoImagen.TURISTA
        )

        if self._grupo_id:
            await self._enviador_foto.enviar(img_interna, self._grupo_id)
            await self._enviador_foto.enviar(img_turista, self._grupo_id)


async def publicar_seguro(service: PublicarListaPreciosServicio) -> None:
    """Best-effort wrapper around publicar().

    - Acquires the module-level concurrency guard; silently skips if already set.
    - Catches and logs any exception from publicar(); never re-raises.
    """
    global _generando
    if _generando:
        logger.debug("publicar_seguro: generation already in progress, skipping")
        return

    _generando = True
    try:
        await service.publicar()
    except Exception:
        logger.exception("publicar_seguro: error during price-list publication")
    finally:
        _generando = False
