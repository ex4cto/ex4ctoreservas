from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes
from garay.infraestructura.persistencia.modelos import ClienteModel
from garay.infraestructura.persistencia.repositorios.ventas import SQLAVentaRepository


def _make_cliente(sf: sessionmaker[Session]) -> uuid.UUID:
    cliente_id = uuid.uuid4()
    with sf.begin() as s:
        s.add(ClienteModel(id=cliente_id, nombre="Test Cliente", tipo="EXTERNO"))
    return cliente_id


def test_guardar_y_buscar_por_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    v = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("500000"),
        neto=Dinero("450000"),
        servicio_ids=[uuid.uuid4(), uuid.uuid4()],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 1),
        participantes=Participantes(
            vendedor_nombre="Maria",
            cerrador_nombre=None,
            punto_de_venta_id=None,
            referido_nombre=None,
        ),
    )
    repo.guardar(v)
    resultado = repo.buscar_por_id(v.id)
    assert resultado is not None
    assert resultado.id == v.id
    assert resultado.valor_venta == Dinero("500000")
    assert len(resultado.servicio_ids) == 2
    assert all(isinstance(uid, uuid.UUID) for uid in resultado.servicio_ids)
    assert resultado.participantes.vendedor_nombre == "Maria"
    assert resultado.tipo_cliente == TipoCliente.EXTERNO


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAVentaRepository(sf)
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_servicio_ids_round_trip(sf: sessionmaker[Session]) -> None:
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    sids = [uuid.uuid4() for _ in range(3)]
    v = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("200000"),
        neto=Dinero("180000"),
        servicio_ids=sids,
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.INTERNO,
        fecha=datetime.date(2026, 7, 2),
        participantes=Participantes(),
    )
    repo.guardar(v)
    resultado = repo.buscar_por_id(v.id)
    assert resultado is not None
    assert set(resultado.servicio_ids) == set(sids)


def test_listar(sf: sessionmaker[Session]) -> None:
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    for i in range(2):
        v = Venta(
            id=uuid.uuid4(),
            valor_venta=Dinero("100000"),
            neto=Dinero("90000"),
            servicio_ids=[],
            cliente_id=cliente_id,
            tipo_cliente=TipoCliente.DIGITAL,
            fecha=datetime.date(2026, 7, i + 1),
            participantes=Participantes(),
        )
        repo.guardar(v)
    assert len(repo.listar()) == 2


def test_listar_por_freelancer_y_periodo_vendedor(sf: sessionmaker[Session]) -> None:
    """Freelancer as vendedor — should be returned."""
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    v = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("500000"),
        neto=Dinero("450000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 15),
        participantes=Participantes(
            vendedor_nombre="Carlos", cerrador_nombre=None,
            punto_de_venta_id=None, referido_nombre=None,
        ),
    )
    repo.guardar(v)
    results = repo.listar_por_freelancer_y_periodo(
        "Carlos", datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
    )
    assert len(results) == 1
    assert results[0].id == v.id


def test_listar_por_freelancer_y_periodo_cerrador(sf: sessionmaker[Session]) -> None:
    """Freelancer as cerrador (OR logic) — should also be returned."""
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    v = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("300000"),
        neto=Dinero("270000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 10),
        participantes=Participantes(
            vendedor_nombre="OtroVendedor", cerrador_nombre="Carlos",
            punto_de_venta_id=None, referido_nombre=None,
        ),
    )
    repo.guardar(v)
    results = repo.listar_por_freelancer_y_periodo(
        "Carlos", datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
    )
    assert len(results) == 1


def test_listar_por_freelancer_y_periodo_fuera_rango(sf: sessionmaker[Session]) -> None:
    """Venta outside date range — should NOT be returned."""
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    v = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("200000"),
        neto=Dinero("180000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 6, 1),
        participantes=Participantes(
            vendedor_nombre="Carlos", cerrador_nombre=None,
            punto_de_venta_id=None, referido_nombre=None,
        ),
    )
    repo.guardar(v)
    results = repo.listar_por_freelancer_y_periodo(
        "Carlos", datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
    )
    assert len(results) == 0


def test_listar_por_periodo(sf: sessionmaker[Session]) -> None:
    """listar_por_periodo returns all ventas within the date range."""
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    for day in (10, 20):
        v = Venta(
            id=uuid.uuid4(),
            valor_venta=Dinero("100000"),
            neto=Dinero("90000"),
            servicio_ids=[],
            cliente_id=cliente_id,
            tipo_cliente=TipoCliente.INTERNO,
            fecha=datetime.date(2026, 7, day),
            participantes=Participantes(),
        )
        repo.guardar(v)
    # One outside range
    v_out = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("100000"),
        neto=Dinero("90000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.INTERNO,
        fecha=datetime.date(2026, 6, 1),
        participantes=Participantes(),
    )
    repo.guardar(v_out)
    results = repo.listar_por_periodo(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))
    assert len(results) == 2
