"""Tests for ConsultaClientes/FacturasService — flattening, TDD RED phase."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

from garay.aplicacion.reportes.consulta_clientes import ConsultaClientesService
from garay.aplicacion.reportes.consulta_facturas import ConsultaFacturasService
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.facturas.entidades import Factura
from garay.dominio.facturas.tipos import EstadoEnvioFactura


def test_consulta_clientes_aplana() -> None:
    clientes = MagicMock()
    clientes.listar.return_value = [
        Cliente(
            id=uuid.uuid4(),
            nombre="Juan Perez",
            tipo=TipoCliente.EXTERNO,
            telefono="3001234567",
            email="juan@example.com",
        )
    ]

    servicio = ConsultaClientesService(clientes=clientes)
    filas = servicio.ejecutar()

    assert len(filas) == 1
    assert filas[0].nombre == "Juan Perez"
    assert filas[0].tipo == "EXTERNO"
    assert filas[0].email == "juan@example.com"


def test_consulta_clientes_sin_datos() -> None:
    clientes = MagicMock()
    clientes.listar.return_value = []
    assert ConsultaClientesService(clientes=clientes).ejecutar() == []


def test_consulta_facturas_aplana() -> None:
    factura = Factura(
        id=uuid.uuid4(),
        numero="GT-20260731-A3F7B2",
        venta_id=uuid.uuid4(),
        cliente_nombre="Juan Perez",
        cliente_email="juan@example.com",
        monto_total=Dinero("500000"),
        abono=Dinero("100000"),
        fecha_emision=datetime.date(2026, 7, 15),
        html_contenido="<html></html>",
        estado_envio=EstadoEnvioFactura.ENVIADO,
    )
    facturas = MagicMock()
    facturas.listar_por_periodo.return_value = [factura]

    servicio = ConsultaFacturasService(facturas=facturas)
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert len(filas) == 1
    assert filas[0].numero == "GT-20260731-A3F7B2"
    assert filas[0].monto_total == Dinero("500000")
    assert filas[0].abono == Dinero("100000")
    assert filas[0].estado_envio == "ENVIADO"
    facturas.listar_por_periodo.assert_called_once_with(
        datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
    )


def test_consulta_facturas_sin_datos() -> None:
    facturas = MagicMock()
    facturas.listar_por_periodo.return_value = []
    servicio = ConsultaFacturasService(facturas=facturas)
    assert servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)) == []
