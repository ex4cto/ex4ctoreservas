"""Application service: edit the tour date of a venta with an audit record."""

from __future__ import annotations

import datetime
import uuid

from garay.aplicacion.ventas.comandos import EditarFechaVentaComando
from garay.dominio.puertos.repositorios import AuditoriaVentaRepository, VentaRepository
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.errores import (
    LimiteEdicionesAlcanzado,
    MotivoRequerido,
    VentaNoEncontrada,
)

# A venta may be edited at most twice; the third edit is blocked. Anular is
# terminal and does not count. When new edit actions appear (e.g. EDITAR_CLIENTE)
# they must be added here so they count toward the same limit.
_MAX_EDICIONES = 2
_ACCIONES_EDICION = frozenset({AccionAuditoria.EDITAR_FECHA})


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

        registros = self._auditoria.listar_por_venta_id(cmd.venta_id)
        ediciones = sum(1 for r in registros if r.accion in _ACCIONES_EDICION)
        if ediciones >= _MAX_EDICIONES:
            raise LimiteEdicionesAlcanzado(
                f"La venta {cmd.venta_id} ya alcanzó el máximo de "
                f"{_MAX_EDICIONES} ediciones permitidas."
            )

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
