from __future__ import annotations

import datetime

from garay.dominio.infraestructura_monitor.entidades import ServicioInfraestructura


def dias_restantes(servicio: ServicioInfraestructura, hoy: datetime.date) -> int:
    """Dias desde 'hoy' hasta la fecha de renovacion (negativo si ya vencio)."""
    return (servicio.fecha_renovacion - hoy).days


def banda_alerta_de_hoy(
    servicio: ServicioInfraestructura, hoy: datetime.date
) -> int | None:
    """Devuelve la banda (p.ej. 30) si 'hoy' cae EXACTAMENTE en una banda de aviso,
    o None si hoy no amerita alerta. Trigger sin estado (exact-day)."""
    restantes = dias_restantes(servicio, hoy)
    return restantes if restantes in servicio.bandas_aviso else None
