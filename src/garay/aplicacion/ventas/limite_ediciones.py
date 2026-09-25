"""Shared edit-limit rule for ventas.

Split into two independent verifiers:
- Financial: counts EDITAR_CANAL + EDITAR_NETO + EDITAR_VALOR_VENTA, MAX=3.
- Informational: no-op (no limit for informational fields).

The backward-compat alias ``verificar_limite_ediciones`` delegates to the
financial verifier so ``editar_canal.py`` (and any other callers) continue
to work without modification. Historical EDITAR_CANAL rows already in the
audit table are counted by the financial verifier because EDITAR_CANAL is in
ACCIONES_FINANCIERAS — no backfill needed.
"""

from __future__ import annotations

import uuid

from garay.dominio.puertos.repositorios import AuditoriaVentaRepository
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import LimiteEdicionesAlcanzado

MAX_EDICIONES_FINANCIERO = 3

ACCIONES_FINANCIERAS = frozenset(
    {
        AccionAuditoria.EDITAR_CANAL,       # historical records count toward financial limit
        AccionAuditoria.EDITAR_NETO,
        AccionAuditoria.EDITAR_VALOR_VENTA,
        AccionAuditoria.EDITAR_SERVICIO,    # changing the tour changes the net amount
    }
)


def verificar_limite_ediciones_financiero(
    auditoria: AuditoriaVentaRepository, venta_id: uuid.UUID
) -> None:
    """Raise LimiteEdicionesAlcanzado when the venta has reached the financial edit cap (MAX=3)."""
    registros = auditoria.listar_por_venta_id(venta_id)
    ediciones = sum(1 for r in registros if r.accion in ACCIONES_FINANCIERAS)
    if ediciones >= MAX_EDICIONES_FINANCIERO:
        raise LimiteEdicionesAlcanzado(
            f"La venta {venta_id} ya alcanzó el máximo de "
            f"{MAX_EDICIONES_FINANCIERO} ediciones financieras permitidas."
        )


def verificar_limite_ediciones_informativo(
    auditoria: AuditoriaVentaRepository, venta_id: uuid.UUID
) -> None:
    """No-op: informational fields (fecha, cliente, participantes) have no edit limit."""
    # Intentionally empty: informational fields are unlimited.
    pass


# Backward-compat alias — delegates to the financial verifier so existing callers
# (editar_canal.py, editar_fecha_venta.py, editar_cliente_venta.py, editar_participantes.py)
# continue to work without modification.
verificar_limite_ediciones = verificar_limite_ediciones_financiero

# Backward-compat name alias for the frozenset (old name: ACCIONES_EDICION).
ACCIONES_EDICION = ACCIONES_FINANCIERAS
