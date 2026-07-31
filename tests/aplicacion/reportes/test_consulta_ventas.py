"""Tests for ConsultaVentasService — FK resolution + flattening, TDD RED phase."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

from garay.aplicacion.reportes.consulta_ventas import ConsultaVentasService
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes


def test_ejecutar_resuelve_fks_y_aplana() -> None:
    cliente_id = uuid.uuid4()
    serv_a = uuid.uuid4()
    serv_b = uuid.uuid4()
    venta = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("500000"),
        neto=Dinero("300000"),
        servicio_ids=[serv_a, serv_b],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.DIGITAL,
        fecha=datetime.date(2026, 7, 10),
        participantes=Participantes(vendedor_nombre="Carlos", cerrador_nombre="Maria"),
        adultos=2,
        ninos=1,
        canal_origen="WhatsApp",
    )
    ventas = MagicMock()
    ventas.listar_por_periodo.return_value = [venta]
    clientes = MagicMock()
    clientes.listar.return_value = [
        Cliente(id=cliente_id, nombre="Juan Perez", tipo=TipoCliente.DIGITAL)
    ]
    servicios = MagicMock()
    servicios.listar.return_value = [
        Servicio(id=serv_a, numero=1, nombre="Tour Islas"),
        Servicio(id=serv_b, numero=2, nombre="City Tour"),
    ]

    servicio = ConsultaVentasService(ventas=ventas, clientes=clientes, servicios=servicios)
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert len(filas) == 1
    fila = filas[0]
    assert fila.cliente_nombre == "Juan Perez"
    assert fila.servicios == "Tour Islas, City Tour"
    assert fila.valor == Dinero("500000")
    assert fila.neto == Dinero("300000")
    assert fila.ganancia == Dinero("200000")
    assert fila.tipo_cliente == "DIGITAL"
    assert fila.canal_origen == "WhatsApp"
    assert fila.vendedor == "Carlos"
    assert fila.cerrador == "Maria"
    assert fila.adultos == 2
    assert fila.ninos == 1
    ventas.listar_por_periodo.assert_called_once_with(
        datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
    )


def test_cliente_desconocido_usa_placeholder() -> None:
    venta = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("100000"),
        neto=Dinero("50000"),
        servicio_ids=[],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 5),
        participantes=Participantes(),
    )
    ventas = MagicMock()
    ventas.listar_por_periodo.return_value = [venta]
    clientes = MagicMock()
    clientes.listar.return_value = []
    servicios = MagicMock()
    servicios.listar.return_value = []

    servicio = ConsultaVentasService(ventas=ventas, clientes=clientes, servicios=servicios)
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert filas[0].cliente_nombre == "—"
    assert filas[0].servicios == ""


def test_sin_ventas_devuelve_vacio() -> None:
    ventas = MagicMock()
    ventas.listar_por_periodo.return_value = []
    clientes = MagicMock()
    clientes.listar.return_value = []
    servicios = MagicMock()
    servicios.listar.return_value = []

    servicio = ConsultaVentasService(ventas=ventas, clientes=clientes, servicios=servicios)
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert filas == []
