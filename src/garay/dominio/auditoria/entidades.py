"""Per-field audit record for edits on money-affecting entities.

One immutable row per changed field: entity type, entity identity, field name,
old value, new value, actor identity, and timestamp.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RegistroAuditoria:
    """Immutable per-field audit record for an edit on a money-affecting entity.

    ``entidad_id`` is used for UUID-keyed entities (servicios, freelancers,
    reglas_comision, puntos_de_venta).
    ``entidad_clave`` is used for text-keyed entities (socios_config.nombre).
    At least one of ``entidad_id`` / ``entidad_clave`` should be non-null per row.
    """

    id: uuid.UUID
    entidad_tipo: str
    entidad_id: uuid.UUID | None
    entidad_clave: str | None
    campo: str
    valor_anterior: str | None
    valor_nuevo: str | None
    realizada_por_telegram_id: int
    realizada_por_nombre: str | None
    realizada_at: datetime.datetime

    def __post_init__(self) -> None:
        if self.realizada_por_telegram_id is None:
            raise ValueError(
                "realizada_por_telegram_id es obligatorio para registros de auditoría"
            )
