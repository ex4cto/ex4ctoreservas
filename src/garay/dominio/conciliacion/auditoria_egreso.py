"""Audit domain entity for manual egreso edits.

One immutable row per field changed: what changed, from/to, who and when.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class AuditoriaEgreso:
    """Immutable per-field audit record for an edit on a manual Egreso."""

    id: uuid.UUID
    egreso_id: uuid.UUID
    campo: str
    valor_anterior: str
    valor_nuevo: str
    realizada_por_telegram_id: int
    realizada_por_nombre: str | None
    realizada_at: datetime.datetime
