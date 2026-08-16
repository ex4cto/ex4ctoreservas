from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class ServicioInfraestructura:
    """Un servicio de infraestructura vigilado por fecha de renovacion."""

    nombre: str
    fecha_renovacion: datetime.date
    bandas_aviso: tuple[int, ...]
