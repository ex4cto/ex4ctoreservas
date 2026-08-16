from __future__ import annotations

import datetime
from dataclasses import FrozenInstanceError

import pytest

from garay.dominio.infraestructura_monitor.entidades import ServicioInfraestructura


class TestServicioInfraestructura:
    def test_construccion_basica(self) -> None:
        servicio = ServicioInfraestructura(
            nombre="Dominio garaytours.com",
            fecha_renovacion=datetime.date(2027, 3, 15),
            bandas_aviso=(60, 30, 7, 1),
        )
        assert servicio.nombre == "Dominio garaytours.com"
        assert servicio.fecha_renovacion == datetime.date(2027, 3, 15)
        assert servicio.bandas_aviso == (60, 30, 7, 1)

    def test_es_dataclass_frozen(self) -> None:
        servicio = ServicioInfraestructura(
            nombre="Dominio garaytours.com",
            fecha_renovacion=datetime.date(2027, 3, 15),
            bandas_aviso=(60, 30, 7, 1),
        )
        with pytest.raises(FrozenInstanceError):
            servicio.nombre = "otro"  # type: ignore[misc]

    def test_bandas_aviso_es_tuple(self) -> None:
        servicio = ServicioInfraestructura(
            nombre="Servidor Railway",
            fecha_renovacion=datetime.date(2027, 6, 1),
            bandas_aviso=(90, 45),
        )
        assert isinstance(servicio.bandas_aviso, tuple)
        assert servicio.bandas_aviso == (90, 45)
