"""Application service: NotificarCambioCatalogoServicio.

Tracks pending catalog changes, debounces a 5-minute reminder DM,
and orchestrates image regeneration + notifications on /actualizar_imagenes.
"""

from __future__ import annotations

import asyncio
import html
import logging

from garay.aplicacion.servicios.lista_precios import PublicarListaPreciosServicio
from garay.dominio.puertos.cambios_imagen import CambioPendiente, CambiosPendientesRepository
from garay.dominio.puertos.notificador_texto import NotificadorTextoPort
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)

# Seconds to wait after the last catalog change before sending a reminder DM.
DEBOUNCE_RECORDATORIO_SEG: int = 300  # 5 minutes


class NotificarCambioCatalogoServicio:
    """Tracks pending catalog changes and orchestrates notifications.

    Responsibilities:
    - Persist each change description to the DB via CambiosPendientesRepository.
    - Debounce a reminder DM: 5 minutes after the last change, DM all destinatarios.
    - On /actualizar_imagenes: call publicar_seguro, send group + confirmation DMs,
      clear the repo.
    - On Playwright error: DM only dev_ids with the error detail.
    """

    def __init__(
        self,
        cambios_repo: CambiosPendientesRepository,
        notificador: NotificadorTextoPort,
        publicar_svc: PublicarListaPreciosServicio,
        destinatarios: list[int],
        dev_ids: list[int],
        grupo_id: str,
    ) -> None:
        self._repo = cambios_repo
        self._notificador = notificador
        self._publicar_svc = publicar_svc
        self._destinatarios = destinatarios
        self._dev_ids = dev_ids
        self._grupo_id = grupo_id
        self._tarea_recordatorio: asyncio.Task[None] | None = None

    async def registrar_cambio(
        self,
        accion: str,
        usuario_nombre: str,
        tour_nombre: str,
    ) -> None:
        """Persist change and (re)start the debounced reminder timer.

        Args:
            accion: One of "editado", "creado", "activado", "desactivado".
            usuario_nombre: Display name of the admin who made the change.
            tour_nombre: Name of the tour affected.
        """
        descripcion = obtener_mensaje(f"catalogo.cambios.{accion}").format(
            usuario=html.escape(usuario_nombre),
            nombre=html.escape(tour_nombre),
        )
        await asyncio.to_thread(self._repo.registrar, descripcion)

        # Cancel any in-flight reminder and restart the debounce window.
        if self._tarea_recordatorio is not None and not self._tarea_recordatorio.done():
            self._tarea_recordatorio.cancel()
        self._tarea_recordatorio = asyncio.create_task(self._enviar_recordatorio())

    async def _enviar_recordatorio(self) -> None:
        """Sleep DEBOUNCE_RECORDATORIO_SEG, then DM destinatarios with pending summary."""
        try:
            await asyncio.sleep(DEBOUNCE_RECORDATORIO_SEG)
        except asyncio.CancelledError:
            return

        cambios = await asyncio.to_thread(self._repo.listar_todos)
        if not cambios:
            return

        texto = self._formatear_recordatorio(cambios)
        for tid in self._destinatarios:
            try:
                await self._notificador.enviar(tid, texto)
            except Exception:
                logger.exception("Error sending reminder to %s", tid)

    def _formatear_recordatorio(self, cambios: list[CambioPendiente]) -> str:
        items = "\n".join(c.descripcion for c in cambios)
        return obtener_mensaje("catalogo.cambios.recordatorio").format(
            n=len(cambios), items=items
        )

    async def generar_y_confirmar(self) -> None:
        """Publish images, notify group and destinatarios, clear the repo.

        Called by the /actualizar_imagenes handler. If there are no pending changes,
        returns immediately if there are no pending changes. On Playwright error,
        notifies only dev_ids.
        """
        cambios = await asyncio.to_thread(self._repo.listar_todos)

        # Cancel any in-flight reminder — we're acting on the changes now.
        if self._tarea_recordatorio is not None and not self._tarea_recordatorio.done():
            self._tarea_recordatorio.cancel()

        if not cambios:
            return

        try:
            await self._publicar_svc.publicar()
        except Exception as exc:
            msg_error = obtener_mensaje("catalogo.cambios.error_dev").format(
                error=str(exc)
            )
            for dev_id in self._dev_ids:
                try:
                    await self._notificador.enviar(dev_id, msg_error)
                except Exception:
                    logger.exception("Error notifying dev %s of image error", dev_id)
            return

        # Send group summary.
        if self._grupo_id:
            items = "\n".join(c.descripcion for c in cambios)
            msg_grupo = obtener_mensaje("catalogo.cambios.grupo").format(items=items)
            try:
                await self._notificador.enviar(int(self._grupo_id), msg_grupo)
            except Exception:
                logger.exception("Error sending group update message")

        # Clear pending changes.
        await asyncio.to_thread(self._repo.limpiar)

        # Confirm to all destinatarios.
        msg_confirm = obtener_mensaje("catalogo.cambios.confirmacion")
        for tid in self._destinatarios:
            try:
                await self._notificador.enviar(tid, msg_confirm)
            except Exception:
                logger.exception("Error sending confirmation to %s", tid)
