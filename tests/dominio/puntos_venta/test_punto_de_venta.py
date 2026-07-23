"""Tests de la entidad PuntoDeVenta."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.puntos_venta.errores import NombrePuntoVacio, PorcentajeCapaInvalido


class TestPuntoDeVenta:
    def test_creacion_valida(self) -> None:
        pdv = PuntoDeVenta(id=uuid.uuid4(), nombre="Oficina Central", porcentaje_capa=Decimal("20"))
        assert pdv.nombre == "Oficina Central"
        assert pdv.porcentaje_capa == Decimal("20")

    def test_porcentaje_cero_invalido(self) -> None:
        with pytest.raises(PorcentajeCapaInvalido):
            PuntoDeVenta(id=uuid.uuid4(), nombre="Punto A", porcentaje_capa=Decimal("0"))

    def test_porcentaje_mayor_cien_invalido(self) -> None:
        with pytest.raises(PorcentajeCapaInvalido):
            PuntoDeVenta(id=uuid.uuid4(), nombre="Punto A", porcentaje_capa=Decimal("101"))

    def test_porcentaje_valido_limite_100(self) -> None:
        pdv = PuntoDeVenta(id=uuid.uuid4(), nombre="Punto A", porcentaje_capa=Decimal("100"))
        assert pdv.porcentaje_capa == Decimal("100")

    def test_nombre_vacio_levanta_error(self) -> None:
        with pytest.raises(NombrePuntoVacio):
            PuntoDeVenta(id=uuid.uuid4(), nombre="", porcentaje_capa=Decimal("20"))

    def test_porcentaje_es_decimal_no_float(self) -> None:
        pdv = PuntoDeVenta(id=uuid.uuid4(), nombre="Punto A", porcentaje_capa=Decimal("15"))
        assert isinstance(pdv.porcentaje_capa, Decimal)
