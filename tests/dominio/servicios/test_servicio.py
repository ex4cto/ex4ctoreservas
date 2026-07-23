"""Tests de la entidad Servicio."""

from __future__ import annotations

import uuid

import pytest

from garay.dominio.servicios.entidades import Servicio
from garay.dominio.servicios.errores import NombreServicioVacio


class TestServicio:
    def test_creacion_valida(self) -> None:
        s = Servicio(id=uuid.uuid4(), nombre="Tour Ciudad")
        assert s.nombre == "Tour Ciudad"

    def test_nombre_vacio_levanta_error(self) -> None:
        with pytest.raises(NombreServicioVacio):
            Servicio(id=uuid.uuid4(), nombre="")

    def test_descripcion_opcional(self) -> None:
        s = Servicio(id=uuid.uuid4(), nombre="Tour", descripcion="Un tour especial")
        assert s.descripcion == "Un tour especial"

        s2 = Servicio(id=uuid.uuid4(), nombre="Tour")
        assert s2.descripcion == ""
