"""TDD RED — WU-2: canal_origen persistence round-trip."""

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


def _venta(cliente_id: uuid.UUID, **kwargs) -> Venta:
    defaults = dict(
        id=uuid.uuid4(),
        valor_venta=Dinero("500000"),
        neto=Dinero("450000"),
        servicio_ids=[uuid.uuid4()],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 1),
        participantes=Participantes(),
    )
    defaults.update(kwargs)
    return Venta(**defaults)


def test_guardar_venta_digital_persiste_canal(sf: sessionmaker[Session]) -> None:
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    v = _venta(cliente_id, canal_origen="TikTok")
    repo.guardar(v)
    resultado = repo.buscar_por_id(v.id)
    assert resultado is not None
    assert resultado.canal_origen == "TikTok"


def test_guardar_venta_interno_persiste_canal_null(sf: sessionmaker[Session]) -> None:
    repo = SQLAVentaRepository(sf)
    cliente_id = _make_cliente(sf)
    v = _venta(cliente_id, tipo_cliente=TipoCliente.INTERNO, canal_origen=None)
    repo.guardar(v)
    resultado = repo.buscar_por_id(v.id)
    assert resultado is not None
    assert resultado.canal_origen is None


def test_reconstruir_venta_historica_sin_canal(sf: sessionmaker[Session]) -> None:
    """Rows with canal_origen=NULL reconstruct to Venta with canal_origen=None."""
    from garay.infraestructura.persistencia.modelos import VentaModel
    from garay.infraestructura.persistencia.repositorios.ventas import to_domain

    cliente_id = _make_cliente(sf)
    venta_id = uuid.uuid4()
    with sf.begin() as session:
        session.add(
            VentaModel(
                id=venta_id,
                valor_venta=Dinero("300000"),
                neto=Dinero("250000"),
                servicio_ids=["00000000-0000-0000-0000-000000000001"],
                cliente_id=cliente_id,
                tipo_cliente="EXTERNO",
                fecha=datetime.date(2026, 1, 1),
                adultos=1,
                ninos=0,
                estado="PENDIENTE",
                vendedor_nombre=None,
                cerrador_nombre=None,
                canal_origen=None,
            )
        )
    with sf.begin() as session:
        m = session.get(VentaModel, venta_id)
        assert m is not None
        domain = to_domain(m)
        assert domain.canal_origen is None
