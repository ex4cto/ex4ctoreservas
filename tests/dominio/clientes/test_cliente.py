"""Tests de la entidad Cliente."""

from __future__ import annotations

import uuid

import pytest

from garay.dominio.clientes.entidades import CampoCliente, Cliente
from garay.dominio.clientes.errores import NombreClienteVacio
from garay.dominio.comun.tipos import TipoCliente


class TestCliente:
    def test_creacion_valida(self) -> None:
        c = Cliente(id=uuid.uuid4(), nombre="Juan Perez", tipo=TipoCliente.EXTERNO)
        assert c.nombre == "Juan Perez"
        assert c.tipo == TipoCliente.EXTERNO

    def test_nombre_vacio_levanta_error(self) -> None:
        with pytest.raises(NombreClienteVacio):
            Cliente(id=uuid.uuid4(), nombre="", tipo=TipoCliente.EXTERNO)

    def test_nombre_solo_espacios_levanta_error(self) -> None:
        with pytest.raises(NombreClienteVacio):
            Cliente(id=uuid.uuid4(), nombre="   ", tipo=TipoCliente.EXTERNO)

    def test_identidad_por_id(self) -> None:
        uid = uuid.uuid4()
        c1 = Cliente(id=uid, nombre="Ana", tipo=TipoCliente.INTERNO)
        c2 = Cliente(id=uid, nombre="Otro Nombre", tipo=TipoCliente.DIGITAL)
        assert c1 == c2
        assert hash(c1) == hash(c2)

    def test_cliente_con_telefono_hotel_habitacion(self) -> None:
        c = Cliente(
            id=uuid.uuid4(),
            nombre="Pedro Lopez",
            tipo=TipoCliente.EXTERNO,
            telefono="099123456",
            hotel="Hotel Sol",
            numero_habitacion="101",
        )
        assert c.telefono == "099123456"
        assert c.hotel == "Hotel Sol"
        assert c.numero_habitacion == "101"

    def test_cliente_campos_opcionales_son_none_por_defecto(self) -> None:
        c = Cliente(id=uuid.uuid4(), nombre="Maria", tipo=TipoCliente.INTERNO)
        assert c.telefono is None
        assert c.hotel is None
        assert c.numero_habitacion is None


class TestActualizarCampo:
    def _cliente(self) -> Cliente:
        return Cliente(id=uuid.uuid4(), nombre="Juan Perez", tipo=TipoCliente.EXTERNO)

    def test_actualiza_telefono(self) -> None:
        c = self._cliente()
        c.actualizar_campo(CampoCliente.TELEFONO, "3001234567")
        assert c.telefono == "3001234567"

    def test_actualiza_nombre(self) -> None:
        c = self._cliente()
        c.actualizar_campo(CampoCliente.NOMBRE, "Pedro Gómez")
        assert c.nombre == "Pedro Gómez"

    def test_actualiza_email_hotel_identificacion_habitacion(self) -> None:
        c = self._cliente()
        c.actualizar_campo(CampoCliente.EMAIL, "a@b.com")
        c.actualizar_campo(CampoCliente.HOTEL, "Hotel Sol")
        c.actualizar_campo(CampoCliente.IDENTIFICACION, "CC123")
        c.actualizar_campo(CampoCliente.NUMERO_HABITACION, "204")
        assert c.email == "a@b.com"
        assert c.hotel == "Hotel Sol"
        assert c.identificacion == "CC123"
        assert c.numero_habitacion == "204"

    def test_recorta_espacios(self) -> None:
        c = self._cliente()
        c.actualizar_campo(CampoCliente.TELEFONO, "  300  ")
        assert c.telefono == "300"

    def test_nombre_vacio_levanta_error(self) -> None:
        c = self._cliente()
        with pytest.raises(NombreClienteVacio):
            c.actualizar_campo(CampoCliente.NOMBRE, "   ")
        assert c.nombre == "Juan Perez"
