"""Shared edit-limit rule for ventas.

A venta may be edited at most ``MAX_EDICIONES`` times; the next edit is blocked.
Anular is terminal and does not count. Every edit-type audit action must be listed
in ``ACCIONES_EDICION`` so it counts toward the same limit, regardless of which
service performs the edit (fecha, cliente, …).
"""

from __future__ import annotations

import uuid

from garay.dominio.puertos.repositorios import AuditoriaVentaRepository
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import LimiteEdicionesAlcanzado

MAX_EDICIONES = 2
ACCIONES_EDICION = frozenset(
    {AccionAuditoria.EDITAR_FECHA, AccionAuditoria.EDITAR_CLIENTE}
)


def verificar_limite_ediciones(
    auditoria: AuditoriaVentaRepository, venta_id: uuid.UUID
) -> None:
    """Raise LimiteEdicionesAlcanzado when the venta already reached the edit cap."""
    registros = auditoria.listar_por_venta_id(venta_id)
    ediciones = sum(1 for r in registros if r.accion in ACCIONES_EDICION)
    if ediciones >= MAX_EDICIONES:
        raise LimiteEdicionesAlcanzado(
            f"La venta {venta_id} ya alcanzó el máximo de "
            f"{MAX_EDICIONES} ediciones permitidas."
        )
