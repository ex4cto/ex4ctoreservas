"""Application service: edit the referido_alias of a venta with an audit record."""

from __future__ import annotations

import datetime
import uuid

from garay.aplicacion.ventas.comandos import EditarReferidoVentaComando
from garay.aplicacion.ventas.limite_ediciones import verificar_limite_ediciones_informativo
from garay.dominio.puertos.repositorios import AuditoriaVentaRepository, VentaRepository
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada


class EditarReferidoVentaService:
    def __init__(
        self,
        ventas: VentaRepository,
        auditoria: AuditoriaVentaRepository,
    ) -> None:
        self._ventas = ventas
        self._auditoria = auditoria

    def ejecutar(self, cmd: EditarReferidoVentaComando) -> None:
        if not cmd.motivo.strip():
            raise MotivoRequerido("Se requiere un motivo para editar el referido.")

        venta = self._ventas.buscar_por_id(cmd.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No se encontró la venta con id={cmd.venta_id}.")

        verificar_limite_ediciones_informativo(self._auditoria, cmd.venta_id)

        datos_previos = {"referido_alias": venta.participantes.referido_alias}

        # Propagates MismoReferido or VentaYaAnulada to caller.
        venta.cambiar_referido(cmd.nuevo_referido_alias)

        registro = AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            accion=AccionAuditoria.EDITAR_REFERIDO,
            motivo=cmd.motivo.strip(),
            realizada_por_telegram_id=cmd.realizada_por_telegram_id,
            realizada_por_nombre=cmd.realizada_por_nombre,
            realizada_at=datetime.datetime.now(datetime.UTC),
            datos_previos=datos_previos,
        )

        self._auditoria.guardar(registro)
        self._ventas.guardar(venta)
