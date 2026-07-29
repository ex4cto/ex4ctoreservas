from __future__ import annotations

from enum import StrEnum


class TipoEgreso(StrEnum):
    AUTOMATICO = "automatico"
    MANUAL = "manual"


class EstadoConciliacion(StrEnum):
    PENDIENTE = "pendiente"
    MATCHEADO = "matcheado"
    SIN_MATCH = "sin_match"
    PERSONAL = "personal"
