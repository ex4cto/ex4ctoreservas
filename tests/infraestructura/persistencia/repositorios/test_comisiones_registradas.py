from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes
from garay.infraestructura.persistencia.modelos import ClienteModel
from garay.infraestructura.persistencia.repositorios.comisiones_registradas import (
    SQLAComisionRegistradaRepository,
)
from garay.infraestructura.persistencia.repositorios.ventas import SQLAVentaRepository


def _make_venta(sf: sessionmaker[Session]) -> uuid.UUID:
    cliente_id = uuid.uuid4()
    with sf.begin() as s:
        s.add(ClienteModel(id=cliente_id, nombre="Test", tipo="EXTERNO"))
    venta_id = uuid.uuid4()
    SQLAVentaRepository(sf).guardar(
        Venta(
            id=venta_id,
            valor_venta=Dinero("1000000"),
            neto=Dinero("900000"),
            servicio_ids=[],
            cliente_id=cliente_id,
            tipo_cliente=TipoCliente.EXTERNO,
            fecha=datetime.date(2026, 7, 1),
            participantes=Participantes(),
        )
    )
    return venta_id


def test_guardar_y_buscar_round_trip(sf: sessionmaker[Session]) -> None:
    venta_id = _make_venta(sf)
    repo = SQLAComisionRegistradaRepository(sf)
    snapshot = SnapshotReglas(
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("20.00"),
        porcentaje_cerrador=Decimal("10.00"),
        porcentaje_referido_maximo=Decimal("5.00"),
        porcentaje_capa_punto=Decimal("8.00"),
    )
    desglose = DesgloseComision(
        vendedor=Dinero("180000"),
        cerrador=Dinero("90000"),
        punto_de_venta=Dinero("72000"),
        referido=Dinero("0"),
        agencia=Dinero("558000"),
        snapshot=snapshot,
    )
    c = ComisionRegistrada(venta_id=venta_id, desglose=desglose, fecha=datetime.date(2026, 7, 1))
    repo.guardar(c)
    resultado = repo.buscar_por_venta_id(venta_id)
    assert resultado is not None
    assert resultado.venta_id == venta_id
    assert resultado.desglose.vendedor == Dinero("180000")
    assert resultado.desglose.agencia == Dinero("558000")
    s = resultado.desglose.snapshot
    assert s.tipo_cliente == TipoCliente.EXTERNO
    assert s.porcentaje_vendedor == Decimal("20.00")
    assert s.porcentaje_capa_punto == Decimal("8.00")


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAComisionRegistradaRepository(sf)
    assert repo.buscar_por_venta_id(uuid.uuid4()) is None


def test_listar_por_venta_ids_vacio() -> None:
    """listar_por_venta_ids([]) returns [] WITHOUT touching DB."""
    # No sf fixture needed — guard must fire before any DB access
    from unittest.mock import MagicMock

    mock_sf = MagicMock()
    repo = SQLAComisionRegistradaRepository(mock_sf)
    result = repo.listar_por_venta_ids([])
    assert result == []
    mock_sf.begin.assert_not_called()


def test_listar_por_venta_ids(sf: sessionmaker[Session]) -> None:
    """listar_por_venta_ids returns all comisiones for given ids."""
    venta_id1 = _make_venta(sf)
    venta_id2 = _make_venta(sf)
    repo = SQLAComisionRegistradaRepository(sf)
    snapshot = SnapshotReglas(
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("20.00"),
        porcentaje_cerrador=Decimal("10.00"),
        porcentaje_referido_maximo=Decimal("5.00"),
        porcentaje_capa_punto=Decimal("8.00"),
    )
    for venta_id in (venta_id1, venta_id2):
        desglose = DesgloseComision(
            vendedor=Dinero("100000"),
            cerrador=Dinero("50000"),
            punto_de_venta=Dinero("40000"),
            referido=Dinero("0"),
            agencia=Dinero("310000"),
            snapshot=snapshot,
        )
        repo.guardar(
            ComisionRegistrada(
                venta_id=venta_id, desglose=desglose, fecha=datetime.date(2026, 7, 1)
            )
        )
    results = repo.listar_por_venta_ids([venta_id1, venta_id2])
    assert len(results) == 2


def test_listar_por_venta_ids_parcial(sf: sessionmaker[Session]) -> None:
    """listar_por_venta_ids with subset of ids returns only matching ones."""
    venta_id1 = _make_venta(sf)
    venta_id2 = _make_venta(sf)
    repo = SQLAComisionRegistradaRepository(sf)
    snapshot = SnapshotReglas(
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("20.00"),
        porcentaje_cerrador=Decimal("10.00"),
        porcentaje_referido_maximo=Decimal("5.00"),
        porcentaje_capa_punto=Decimal("8.00"),
    )
    for venta_id in (venta_id1, venta_id2):
        desglose = DesgloseComision(
            vendedor=Dinero("100000"),
            cerrador=Dinero("50000"),
            punto_de_venta=Dinero("40000"),
            referido=Dinero("0"),
            agencia=Dinero("310000"),
            snapshot=snapshot,
        )
        repo.guardar(
            ComisionRegistrada(
                venta_id=venta_id, desglose=desglose, fecha=datetime.date(2026, 7, 1)
            )
        )
    results = repo.listar_por_venta_ids([venta_id1])
    assert len(results) == 1
    assert results[0].venta_id == venta_id1
