"""Application service: anular (soft-delete) a venta with an audit record."""

from __future__ import annotations

import datetime
import uuid

from garay.aplicacion.ventas.comandos import AnularVentaComando
from garay.dominio.puertos.repositorios import AuditoriaVentaRepository, VentaRepository
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada


class AnularVentaService:
    def __init__(
        self,
        ventas: VentaRepository,
        auditoria: AuditoriaVentaRepository,
    ) -> None:
        self._ventas = ventas
        self._auditoria = auditoria

    def ejecutar(self, cmd: AnularVentaComando) -> None:
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para anular la venta.")

        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        # Propagates VentaYaAnulada if already anulada — mutates in memory only, no DB write yet.
        venta.anular()

        # Build and persist the audit record BEFORE committing the anulada state so
        # the venta row is never anulada in the DB without a corresponding audit row.
        registro = AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            accion=AccionAuditoria.ANULAR,
            motivo=cmd.motivo.strip(),
            realizada_por_telegram_id=cmd.realizada_por_telegram_id,
            realizada_por_nombre=cmd.realizada_por_nombre,
            realizada_at=datetime.datetime.now(datetime.UTC),
            datos_previos=None,
        )
        self._auditoria.guardar(registro)

        # Persist the anulada venta only after the audit row is safely committed.
        # Residual risk: if this call fails, an orphan audit row exists but the venta
        # stays active (retryable) — this does NOT violate the invariant.
        self._ventas.guardar(venta)
