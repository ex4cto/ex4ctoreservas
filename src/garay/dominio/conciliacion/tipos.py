from __future__ import annotations

from enum import StrEnum


class CategoriaEgreso(StrEnum):
    ARRIENDO = "arriendo"
    NOMINA = "nomina"
    UNIFORMES = "uniformes"
    PAPELERIA = "papeleria"
    PROVEEDOR = "proveedor"
    OCASIONAL = "ocasional"
    OTRO = "otro"


class TipoEgreso(StrEnum):
    AUTOMATICO = "automatico"
    MANUAL = "manual"


class EstadoConciliacion(StrEnum):
    PENDIENTE = "pendiente"
    MATCHEADO = "matcheado"
    SIN_MATCH = "sin_match"
    PERSONAL = "personal"
