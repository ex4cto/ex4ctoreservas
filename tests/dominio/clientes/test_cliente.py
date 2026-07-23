"""Tests de la entidad Cliente."""

from __future__ import annotations

import uuid

import pytest

from garay.dominio.clientes.entidades import Cliente
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
