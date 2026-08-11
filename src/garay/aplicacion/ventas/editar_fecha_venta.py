"""Application service: edit the tour date of a venta with an audit record."""

from __future__ import annotations

import datetime
import uuid

from garay.aplicacion.ventas.comandos import EditarFechaVentaComando
from garay.dominio.puertos.repositorios import AuditoriaVentaRepository, VentaRepository
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada


class EditarFechaVentaService:
    def __init__(
        self,
        ventas: VentaRepository,
        auditoria: AuditoriaVentaRepository,
    ) -> None:
        self._ventas = ventas
        self._auditoria = auditoria

    def ejecutar(self, cmd: EditarFechaVentaComando) -> None:
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para editar la fecha de la venta.")

        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        # Capture the old fecha BEFORE mutating — this becomes datos_previos.
        datos_previos = {"fecha": venta.fecha.isoformat()}

        # Mutates in memory only; propagates VentaYaAnulada if the venta is anulada.
        venta.cambiar_fecha(cmd.nueva_fecha)

        # Build the audit record with the captured previous state.
        registro = AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            accion=AccionAuditoria.EDITAR_FECHA,
            motivo=cmd.motivo.strip(),
            realizada_por_telegram_id=cmd.realizada_por_telegram_id,
            realizada_por_nombre=cmd.realizada_por_nombre,
            realizada_at=datetime.datetime.now(datetime.UTC),
            datos_previos=datos_previos,
        )

        # AUDIT-FIRST: persist the audit row before the venta so the venta row is
        # never updated in the DB without a corresponding audit entry.
        self._auditoria.guardar(registro)
        self._ventas.guardar(venta)
