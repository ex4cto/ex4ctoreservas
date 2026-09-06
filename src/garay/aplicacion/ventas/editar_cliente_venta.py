"""Application service: edit a client data field of a venta with an audit record.

Editing acts on the shared Cliente entity (option A): the change is reflected in
every venta of that client. The change is recorded against the venta the user is
managing, and counts toward that venta's edit limit.
"""

from __future__ import annotations

import datetime
import uuid

from garay.aplicacion.ventas.comandos import EditarClienteVentaComando
from garay.aplicacion.ventas.limite_ediciones import verificar_limite_ediciones
from garay.dominio.clientes.errores import ClienteNoEncontrado
from garay.dominio.puertos.repositorios import (
    AuditoriaVentaRepository,
    ClienteRepository,
    VentaRepository,
)
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada


class EditarClienteVentaService:
    def __init__(
        self,
        ventas: VentaRepository,
        clientes: ClienteRepository,
        auditoria: AuditoriaVentaRepository,
    ) -> None:
        self._ventas = ventas
        self._clientes = clientes
        self._auditoria = auditoria

    def ejecutar(self, cmd: EditarClienteVentaComando) -> None:
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para editar los datos del cliente.")

        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        verificar_limite_ediciones(self._auditoria, cmd.venta_id)

        cliente = self._clientes.buscar_por_id(venta.cliente_id)
        if cliente is None:
            raise ClienteNoEncontrado(
                f"No se encontró el cliente con id={venta.cliente_id}."
            )

        # Capture the old value BEFORE mutating — this becomes datos_previos.
        datos_previos = {cmd.campo.value: getattr(cliente, cmd.campo.value)}

        cliente.actualizar_campo(cmd.campo, cmd.nuevo_valor)

        registro = AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            accion=AccionAuditoria.EDITAR_CLIENTE,
            motivo=cmd.motivo.strip(),
            realizada_por_telegram_id=cmd.realizada_por_telegram_id,
            realizada_por_nombre=cmd.realizada_por_nombre,
            realizada_at=datetime.datetime.now(datetime.UTC),
            datos_previos=datos_previos,
        )

        # AUDIT-FIRST: persist the audit row before the cliente so the cliente is
        # never updated in the DB without a corresponding audit entry.
        self._auditoria.guardar(registro)
        self._clientes.guardar(cliente)
