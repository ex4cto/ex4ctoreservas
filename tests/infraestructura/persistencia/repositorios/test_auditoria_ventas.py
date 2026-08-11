"""Tests for SQLAAuditoriaVentaRepository."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.infraestructura.persistencia.modelos import ClienteModel, VentaModel
from garay.infraestructura.persistencia.repositorios.auditoria_ventas import (
    SQLAAuditoriaVentaRepository,
)


def _make_cliente(sf: sessionmaker[Session]) -> uuid.UUID:
    cliente_id = uuid.uuid4()
    with sf.begin() as s:
        s.add(ClienteModel(id=cliente_id, nombre="Test Cliente", tipo="EXTERNO"))
    return cliente_id


def _make_venta(sf: sessionmaker[Session], cliente_id: uuid.UUID) -> uuid.UUID:
    venta_id = uuid.uuid4()
    with sf.begin() as s:
        s.add(
            VentaModel(
                id=venta_id,
                valor_venta=Dinero("500000"),
                neto=Dinero("450000"),
                abono=None,
                servicio_ids=[],
                cliente_id=cliente_id,
                tipo_cliente="EXTERNO",
                fecha=datetime.date(2026, 8, 11),
                adultos=1,
                ninos=0,
                estado="PENDIENTE",
            )
        )
    return venta_id


def test_guardar_y_listar_por_venta_id(sf: sessionmaker[Session]) -> None:
    """guardar then listar_por_venta_id returns the record with all fields intact."""
    cliente_id = _make_cliente(sf)
    venta_id = _make_venta(sf, cliente_id)
    repo = SQLAAuditoriaVentaRepository(sf)

    audit_id = uuid.uuid4()
    at = datetime.datetime(2026, 8, 11, 10, 0, 0)
    datos = {"valor_venta": "500000", "estado": "PENDIENTE"}

    registro = AuditoriaVenta(
        id=audit_id,
        venta_id=venta_id,
        accion=AccionAuditoria.ANULAR,
        motivo="Anulado por error del cliente",
        realizada_por_telegram_id=123456789,
        realizada_por_nombre="Admin",
        realizada_at=at,
        datos_previos=datos,
    )
    repo.guardar(registro)

    results = repo.listar_por_venta_id(venta_id)
    assert len(results) == 1
    r = results[0]
    assert r.id == audit_id
    assert r.venta_id == venta_id
    assert r.accion == AccionAuditoria.ANULAR
    assert r.motivo == "Anulado por error del cliente"
    assert r.realizada_por_telegram_id == 123456789
    assert r.realizada_por_nombre == "Admin"
    assert r.realizada_at == at
    assert r.datos_previos == datos


def test_listar_por_venta_id_sin_registros(sf: sessionmaker[Session]) -> None:
    """listar_por_venta_id returns [] for a venta with no audit records."""
    repo = SQLAAuditoriaVentaRepository(sf)
    results = repo.listar_por_venta_id(uuid.uuid4())
    assert results == []


def test_listar_por_venta_id_datos_previos_none(sf: sessionmaker[Session]) -> None:
    """datos_previos=None round-trips correctly."""
    cliente_id = _make_cliente(sf)
    venta_id = _make_venta(sf, cliente_id)
    repo = SQLAAuditoriaVentaRepository(sf)

    registro = AuditoriaVenta(
        id=uuid.uuid4(),
        venta_id=venta_id,
        accion=AccionAuditoria.EDITAR_FECHA,
        motivo="Cambio de fecha",
        realizada_por_telegram_id=987654321,
        realizada_por_nombre=None,
        realizada_at=datetime.datetime(2026, 8, 11, 12, 0, 0),
        datos_previos=None,
    )
    repo.guardar(registro)

    results = repo.listar_por_venta_id(venta_id)
    assert len(results) == 1
    assert results[0].datos_previos is None
    assert results[0].realizada_por_nombre is None


def test_listar_por_venta_id_ordered_by_realizada_at(sf: sessionmaker[Session]) -> None:
    """Multiple audit records are returned ordered by realizada_at ascending."""
    cliente_id = _make_cliente(sf)
    venta_id = _make_venta(sf, cliente_id)
    repo = SQLAAuditoriaVentaRepository(sf)

    at1 = datetime.datetime(2026, 8, 11, 8, 0, 0)
    at2 = datetime.datetime(2026, 8, 11, 10, 0, 0)

    repo.guardar(
        AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=venta_id,
            accion=AccionAuditoria.EDITAR_FECHA,
            motivo="First",
            realizada_por_telegram_id=1,
            realizada_por_nombre=None,
            realizada_at=at1,
        )
    )
    repo.guardar(
        AuditoriaVenta(
            id=uuid.uuid4(),
            venta_id=venta_id,
            accion=AccionAuditoria.ANULAR,
            motivo="Second",
            realizada_por_telegram_id=2,
            realizada_por_nombre=None,
            realizada_at=at2,
        )
    )

    results = repo.listar_por_venta_id(venta_id)
    assert len(results) == 2
    assert results[0].realizada_at == at1
    assert results[1].realizada_at == at2
