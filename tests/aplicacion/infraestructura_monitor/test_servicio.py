"""Tests for MonitorServiciosInfraestructuraService.avisos_para.

Covers AC-4 through AC-7 / Seams 4-7.
Pure list assertions — no notifier, no mocks, inject hoy directly.
"""

from __future__ import annotations

import datetime

from garay.aplicacion.infraestructura_monitor.servicio import (
    AvisoRenovacion,
    MonitorServiciosInfraestructuraService,
)
from garay.dominio.infraestructura_monitor.entidades import ServicioInfraestructura

_RENOVACION = datetime.date(2027, 3, 15)
_BANDAS = (60, 30, 7, 1)


def _servicio(
    nombre: str = "Dominio garaytours.com",
    fecha: datetime.date = _RENOVACION,
    bandas: tuple[int, ...] = _BANDAS,
) -> ServicioInfraestructura:
    return ServicioInfraestructura(
        nombre=nombre,
        fecha_renovacion=fecha,
        bandas_aviso=bandas,
    )


class TestAvisosPara:
    def test_un_servicio_due_devuelve_aviso(self) -> None:
        """AC-4: one service due today returns one AvisoRenovacion."""
        # 30 dias antes de 2027-03-15 = 2027-02-13
        servicio = _servicio()
        service = MonitorServiciosInfraestructuraService(servicios=[servicio])
        hoy = datetime.date(2027, 2, 13)

        resultado = service.avisos_para(hoy)

        assert len(resultado) == 1
        assert resultado[0] == AvisoRenovacion(servicio=servicio, banda=30)

    def test_servicio_no_due_devuelve_lista_vacia(self) -> None:
        """AC-5: service not due today returns []."""
        servicio = _servicio()
        service = MonitorServiciosInfraestructuraService(servicios=[servicio])
        # 45 dias antes — not a band
        hoy = datetime.date(2027, 1, 29)

        resultado = service.avisos_para(hoy)

        assert resultado == []

    def test_lista_vacia_de_servicios_devuelve_lista_vacia(self) -> None:
        """AC-6: empty services list returns []."""
        service = MonitorServiciosInfraestructuraService(servicios=[])
        hoy = datetime.date(2027, 2, 13)

        resultado = service.avisos_para(hoy)

        assert resultado == []

    def test_multiples_servicios_solo_los_due(self) -> None:
        """AC-7: multiple services, only due ones returned."""
        # Service 1: due at band 60 on 2027-01-14
        s1 = _servicio(nombre="Dominio garaytours.com")
        # Service 2: has different renewal date — 60 days before 2027-06-01 = 2027-04-02
        s2 = _servicio(nombre="Servidor Railway", fecha=datetime.date(2027, 6, 1))
        service = MonitorServiciosInfraestructuraService(servicios=[s1, s2])
        # On 2027-01-14: s1 is at band 60, s2 is not at any band
        hoy = datetime.date(2027, 1, 14)

        resultado = service.avisos_para(hoy)

        assert len(resultado) == 1
        assert resultado[0].servicio is s1
        assert resultado[0].banda == 60
