"""Tests for SQLAFacturaRepository — TDD RED phase."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.facturas.entidades import Factura
from garay.dominio.facturas.tipos import EstadoEnvioFactura
from garay.infraestructura.persistencia.repositorios.facturas import SQLAFacturaRepository

_ABONO_DEFECTO = Dinero("100000")


def _make_factura(
    *,
    id: uuid.UUID | None = None,
    venta_id: uuid.UUID | None = None,
    numero: str = "GT-20260731-A3F7B2",
    fecha: datetime.date = datetime.date(2026, 7, 15),
    estado: EstadoEnvioFactura = EstadoEnvioFactura.PENDIENTE,
    abono: Dinero | None = _ABONO_DEFECTO,
) -> Factura:
    return Factura(
        id=id or uuid.uuid4(),
        numero=numero,
        venta_id=venta_id or uuid.uuid4(),
        cliente_nombre="Juan Perez",
        cliente_email="juan@example.com",
        monto_total=Dinero("500000"),
        abono=abono,
        fecha_emision=fecha,
        html_contenido="<html>factura</html>",
        estado_envio=estado,
    )


def test_guardar_y_buscar_por_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAFacturaRepository(sf)
    factura = _make_factura()

    repo.guardar(factura)
    resultado = repo.buscar_por_id(factura.id)

    assert resultado is not None
    assert resultado.id == factura.id
    assert resultado.numero == "GT-20260731-A3F7B2"
    assert resultado.venta_id == factura.venta_id
    assert resultado.cliente_nombre == "Juan Perez"
    assert resultado.cliente_email == "juan@example.com"
    assert resultado.monto_total == Dinero("500000")
    assert resultado.abono == Dinero("100000")
    assert resultado.fecha_emision == datetime.date(2026, 7, 15)
    assert resultado.html_contenido == "<html>factura</html>"
    assert resultado.estado_envio is EstadoEnvioFactura.PENDIENTE


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAFacturaRepository(sf)
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_buscar_por_venta_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAFacturaRepository(sf)
    venta_id = uuid.uuid4()
    factura = _make_factura(venta_id=venta_id)
    repo.guardar(factura)

    resultado = repo.buscar_por_venta_id(venta_id)

    assert resultado is not None
    assert resultado.venta_id == venta_id


def test_buscar_por_venta_id_inexistente(sf: sessionmaker[Session]) -> None:
    repo = SQLAFacturaRepository(sf)
    assert repo.buscar_por_venta_id(uuid.uuid4()) is None


def test_guardar_actualiza_estado_misma_fila(sf: sessionmaker[Session]) -> None:
    repo = SQLAFacturaRepository(sf)
    factura = _make_factura(estado=EstadoEnvioFactura.PENDIENTE)
    repo.guardar(factura)

    factura.estado_envio = EstadoEnvioFactura.ENVIADO
    repo.guardar(factura)

    resultado = repo.buscar_por_id(factura.id)
    assert resultado is not None
    assert resultado.estado_envio is EstadoEnvioFactura.ENVIADO


def test_abono_none_persiste(sf: sessionmaker[Session]) -> None:
    repo = SQLAFacturaRepository(sf)
    factura = _make_factura(abono=None)
    repo.guardar(factura)

    resultado = repo.buscar_por_id(factura.id)
    assert resultado is not None
    assert resultado.abono is None


def test_listar_por_periodo_filtra_por_fecha_emision(sf: sessionmaker[Session]) -> None:
    repo = SQLAFacturaRepository(sf)
    dentro = _make_factura(numero="GT-DENTRO", fecha=datetime.date(2026, 7, 10))
    fuera = _make_factura(numero="GT-FUERA", fecha=datetime.date(2026, 6, 30))
    repo.guardar(dentro)
    repo.guardar(fuera)

    resultado = repo.listar_por_periodo(
        datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
    )

    ids = {f.id for f in resultado}
    assert dentro.id in ids
    assert fuera.id not in ids


def test_listar_por_periodo_sin_datos(sf: sessionmaker[Session]) -> None:
    repo = SQLAFacturaRepository(sf)
    assert repo.listar_por_periodo(
        datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
    ) == []
