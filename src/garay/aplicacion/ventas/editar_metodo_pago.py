"""Application service: edit the metodo_pago of a venta with an audit record."""

from __future__ import annotations

import datetime
import uuid

from garay.aplicacion.ventas.comandos import EditarMetodoPagoVentaComando
from garay.aplicacion.ventas.limite_ediciones import verificar_limite_ediciones_informativo
from garay.dominio.puertos.repositorios import AuditoriaVentaRepository, VentaRepository
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada


class EditarMetodoPagoVentaService:
    def __init__(
        self,
        ventas: VentaRepository,
        auditoria: AuditoriaVentaRepository,
    ) -> None:
        self._ventas = ventas
        self._auditoria = auditoria

    def ejecutar(self, cmd: EditarMetodoPagoVentaComando) -> None:
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para editar el método de pago.")

        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        verificar_limite_ediciones_informativo(self._auditoria, cmd.venta_id)

        # Capture the old metodo_pago BEFORE mutating — this becomes datos_previos.
        datos_previos = {
            "metodo_pago": venta.metodo_pago.value if venta.metodo_pago is not None else None
        }

        # Mutates in memory only; propagates VentaYaAnulada or MismoMetodoPago to caller.
        venta.cambiar_metodo_pago(cmd.nuevo_metodo_pago)

        # Build the audit record with the captured previous state.
        registro = AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            accion=AccionAuditoria.EDITAR_METODO_PAGO,
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
