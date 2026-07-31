"""Tests de la entidad Servicio."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from garay.dominio.servicios.entidades import Servicio
from garay.dominio.servicios.errores import NombreServicioVacio, NumeroServicioInvalido


class TestServicio:
    def test_creacion_valida(self) -> None:
        s = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour Ciudad")
        assert s.nombre == "Tour Ciudad"

    def test_nombre_vacio_levanta_error(self) -> None:
        with pytest.raises(NombreServicioVacio):
            Servicio(id=uuid.uuid4(), numero=1, nombre="")

    def test_descripcion_opcional(self) -> None:
        s = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour", descripcion="Un tour especial")
        assert s.descripcion == "Un tour especial"

        s2 = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour")
        assert s2.descripcion == ""

    def test_activo_por_defecto(self) -> None:
        s = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour")
        assert s.activo is True

    def test_numero_invalido_levanta_error(self) -> None:
        with pytest.raises(NumeroServicioInvalido):
            Servicio(id=uuid.uuid4(), numero=0, nombre="Tour")

    def test_numero_valido(self) -> None:
        s = Servicio(id=uuid.uuid4(), numero=137, nombre="Tour")
        assert s.numero == 137

    def test_servicio_con_precios(self) -> None:
        s = Servicio(
            id=uuid.uuid4(),
            numero=1,
            nombre="Tour",
            precio_neto_adulto=Decimal("100"),
            precio_neto_nino=Decimal("50"),
        )
        assert s.precio_neto_adulto == Decimal("100")
        assert s.precio_neto_nino == Decimal("50")

    def test_servicio_sin_precio_nino(self) -> None:
        s = Servicio(
            id=uuid.uuid4(),
            numero=1,
            nombre="Tour",
            precio_neto_adulto=Decimal("100"),
            precio_neto_nino=None,
        )
        assert s.precio_neto_adulto == Decimal("100")
        assert s.precio_neto_nino is None

    def test_servicio_sin_ningun_precio(self) -> None:
        s = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour")
        assert s.precio_neto_adulto is None
        assert s.precio_neto_nino is None

    def test_categoria_opcional(self) -> None:
        s = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour", categoria="TOURS BAHIA")
        assert s.categoria == "TOURS BAHIA"

        s2 = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour")
        assert s2.categoria == ""
