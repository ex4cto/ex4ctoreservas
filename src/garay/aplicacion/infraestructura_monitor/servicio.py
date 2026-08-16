"""Application service for infrastructure services monitor.

Orchestrates domain date-math to produce due-today renewal alerts.
No I/O: the service returns a list of AvisoRenovacion for the infra layer
to deliver via Telegram.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from garay.dominio.infraestructura_monitor.entidades import ServicioInfraestructura
from garay.dominio.infraestructura_monitor.servicio import banda_alerta_de_hoy


@dataclass(frozen=True)
class AvisoRenovacion:
    """Resultado listo para notificar: que servicio y en que banda."""

    servicio: ServicioInfraestructura
    banda: int


class MonitorServiciosInfraestructuraService:
    """Corre la logica de dominio para 'hoy' y devuelve los avisos debidos.

    No hace I/O — el infra decide como enviarlos.
    """

    def __init__(self, servicios: list[ServicioInfraestructura]) -> None:
        self._servicios = servicios

    def avisos_para(self, hoy: datetime.date) -> list[AvisoRenovacion]:
        """Retorna los avisos cuya banda de alerta cae exactamente en 'hoy'.

        Args:
            hoy: Fecha a evaluar (inyectada; normalmente la fecha actual en Bogota).

        Returns:
            Lista de AvisoRenovacion (vacia si ningun servicio requiere alerta hoy).
        """
        avisos: list[AvisoRenovacion] = []
        for s in self._servicios:
            banda = banda_alerta_de_hoy(s, hoy)
            if banda is not None:
                avisos.append(AvisoRenovacion(servicio=s, banda=banda))
        return avisos
