from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes
from garay.infraestructura.persistencia.modelos import ClienteModel, FreelancerModel, VentaModel
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


_UUID_F = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
_UUID_OTHER = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
_UUID_OTHER2 = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


def test_listar_por_freelancer_y_periodo_vendedor(sf: sessionmaker[Session]) -> None:
    """Freelancer as vendedor by name (NULL id) — should be returned."""
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
            vendedor_nombre="Carlos",
            cerrador_nombre=None,
            punto_de_venta_id=None,
            referido_nombre=None,
        ),
    )
    repo.guardar(v)
    results = repo.listar_por_freelancer_y_periodo(
        freelancer_id=_UUID_OTHER,
        nombre="Carlos",
        desde=datetime.date(2026, 7, 1),
        hasta=datetime.date(2026, 7, 31),
    )
    assert len(results) == 1
    assert results[0].id == v.id


def test_listar_por_freelancer_y_periodo_cerrador(sf: sessionmaker[Session]) -> None:
    """Freelancer as cerrador by name (NULL id) — should also be returned."""
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
            vendedor_nombre="OtroVendedor",
            cerrador_nombre="Carlos",
            punto_de_venta_id=None,
            referido_nombre=None,
        ),
    )
    repo.guardar(v)
    results = repo.listar_por_freelancer_y_periodo(
        freelancer_id=_UUID_OTHER,
        nombre="Carlos",
        desde=datetime.date(2026, 7, 1),
        hasta=datetime.date(2026, 7, 31),
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
            vendedor_nombre="Carlos",
            cerrador_nombre=None,
            punto_de_venta_id=None,
            referido_nombre=None,
        ),
    )
    repo.guardar(v)
    results = repo.listar_por_freelancer_y_periodo(
        freelancer_id=_UUID_OTHER,
        nombre="Carlos",
        desde=datetime.date(2026, 7, 1),
        hasta=datetime.date(2026, 7, 31),
    )
    assert len(results) == 0


def test_listar_por_freelancer_y_periodo_id_linked(sf: sessionmaker[Session]) -> None:
    """SC-13 partial: venta with vendedor_id=UUID_F is returned when queried by id."""
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    f_id = _make_freelancer(sf)
    v = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("500000"),
        neto=Dinero("400000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 15),
        participantes=Participantes(
            vendedor_nombre="other_name",
            vendedor_id=f_id,
        ),
    )
    repo.guardar(v)
    results = repo.listar_por_freelancer_y_periodo(
        freelancer_id=f_id,
        nombre="different",  # name doesn't match but id does
        desde=datetime.date(2026, 7, 1),
        hasta=datetime.date(2026, 7, 31),
    )
    assert len(results) == 1
    assert results[0].id == v.id


def test_listar_por_freelancer_y_periodo_null_id_name_match(sf: sessionmaker[Session]) -> None:
    """Name match only when vendedor_id IS NULL."""
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    v = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("400000"),
        neto=Dinero("300000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 15),
        participantes=Participantes(
            vendedor_nombre="Kike",
            vendedor_id=None,
        ),
    )
    repo.guardar(v)
    results = repo.listar_por_freelancer_y_periodo(
        freelancer_id=_UUID_OTHER,  # different id — will NOT match by id
        nombre="Kike",
        desde=datetime.date(2026, 7, 1),
        hasta=datetime.date(2026, 7, 31),
    )
    assert len(results) == 1
    assert results[0].id == v.id


def test_listar_por_freelancer_y_periodo_excludes_different_id_name_collision(
    sf: sessionmaker[Session],
) -> None:
    """SC-13 override: row with vendedor_id=UUID_OTHER2 and name='Kike' is NOT returned
    when querying with freelancer_id=UUID_F, nombre='Kike', because id is NOT NULL
    and doesn't match UUID_F."""
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    other_f_id = _make_freelancer(sf)  # some other freelancer id
    f_id = _make_freelancer(sf)  # the querying freelancer
    v = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("300000"),
        neto=Dinero("200000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 15),
        participantes=Participantes(
            vendedor_nombre="Kike",
            vendedor_id=other_f_id,  # non-NULL id, belongs to someone else
        ),
    )
    repo.guardar(v)
    results = repo.listar_por_freelancer_y_periodo(
        freelancer_id=f_id,
        nombre="Kike",
        desde=datetime.date(2026, 7, 1),
        hasta=datetime.date(2026, 7, 31),
    )
    # NOT returned: vendedor_id is not NULL and doesn't match f_id; name match is skipped
    assert len(results) == 0


def _make_freelancer(sf: sessionmaker[Session]) -> uuid.UUID:
    """Insert a FreelancerModel row so FK constraints are satisfied."""
    f_id = uuid.uuid4()
    with sf.begin() as s:
        s.add(
            FreelancerModel(
                id=f_id,
                nombre="Test Freelancer",
                activo=True,
                telegram_user_id=None,
                es_admin=False,
            )
        )
    return f_id


def test_vendedor_id_cerrador_id_round_trip(sf: sessionmaker[Session]) -> None:
    """Slice B: guardar a Venta with vendedor_id/cerrador_id and load it back preserves both ids."""
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    f1_id = _make_freelancer(sf)
    f2_id = _make_freelancer(sf)

    v = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("600000"),
        neto=Dinero("540000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 8, 1),
        participantes=Participantes(
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
            vendedor_id=f1_id,
            cerrador_id=f2_id,
        ),
    )
    repo.guardar(v)
    resultado = repo.buscar_por_id(v.id)

    assert resultado is not None
    assert resultado.participantes.vendedor_id == f1_id
    assert resultado.participantes.cerrador_id == f2_id
    assert resultado.participantes.vendedor_nombre == "Ana"
    assert resultado.participantes.cerrador_nombre == "Luis"


def test_historical_null_ids_load_as_none(sf: sessionmaker[Session]) -> None:
    """Slice B: a VentaModel row with null ids loads with vendedor_id=None, cerrador_id=None."""
    cliente_id = _make_cliente(sf)
    venta_id = uuid.uuid4()

    with sf.begin() as s:
        s.add(
            VentaModel(
                id=venta_id,
                valor_venta=Dinero("100000"),
                neto=Dinero("90000"),
                abono=None,
                servicio_ids=[],
                cliente_id=cliente_id,
                tipo_cliente="EXTERNO",
                fecha=datetime.date(2026, 7, 1),
                adultos=1,
                ninos=0,
                estado="PENDIENTE",
                vendedor_nombre="Kike",
                cerrador_nombre=None,
                vendedor_id=None,
                cerrador_id=None,
            )
        )

    repo = SQLAVentaRepository(sf)
    resultado = repo.buscar_por_id(venta_id)

    assert resultado is not None
    assert resultado.participantes.vendedor_id is None
    assert resultado.participantes.cerrador_id is None
    assert resultado.participantes.vendedor_nombre == "Kike"


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
