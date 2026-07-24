from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.tiquetera.entidades import Tiquetera
from garay.dominio.tiquetera.valor_objetos import DatosExtraidos
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes
from garay.infraestructura.persistencia.modelos import ClienteModel
from garay.infraestructura.persistencia.repositorios.tiqueteras import SQLATiqueteraRepository
from garay.infraestructura.persistencia.repositorios.ventas import SQLAVentaRepository


def _make_venta(sf: sessionmaker[Session]) -> uuid.UUID:
    cliente_id = uuid.uuid4()
    with sf.begin() as s:
        s.add(ClienteModel(id=cliente_id, nombre="Test", tipo="EXTERNO"))
    venta_id = uuid.uuid4()
    venta_repo = SQLAVentaRepository(sf)
    venta = Venta(
        id=venta_id,
        valor_venta=Dinero("300000"),
        neto=Dinero("270000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 1),
        participantes=Participantes(),
    )
    venta_repo.guardar(venta)
    return venta_id


def test_guardar_y_buscar_sin_datos_extraidos(sf: sessionmaker[Session]) -> None:
    venta_id = _make_venta(sf)
    repo = SQLATiqueteraRepository(sf)
    t = Tiquetera(id=uuid.uuid4(), venta_id=venta_id, foto_referencia="foto.jpg")
    repo.guardar(t)
    resultado = repo.buscar_por_venta_id(venta_id)
    assert resultado is not None
    assert resultado.venta_id == venta_id
    assert resultado.datos_extraidos is None
    assert resultado.procesada is False


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLATiqueteraRepository(sf)
    assert repo.buscar_por_venta_id(uuid.uuid4()) is None


def test_round_trip_con_datos_extraidos(sf: sessionmaker[Session]) -> None:
    venta_id = _make_venta(sf)
    repo = SQLATiqueteraRepository(sf)
    datos = DatosExtraidos(
        valor_venta=Dinero("500000"),
        neto=Dinero("450000"),
        abono=None,
        nombre_cliente="Juan",
        telefono="3001234567",
        cliente_hotel="Hotel Hilton",
        numero_habitacion="305",
        servicio_nombre="City Tour",
        destinos=("Cartagena", "Santa Marta"),
        fecha_salida=datetime.datetime(2026, 8, 1, 9, 0),
        adultos=2,
        ninos=1,
        numero_ticket=None,
        confianza=Decimal("0.95"),
    )
    t = Tiquetera(
        id=uuid.uuid4(), venta_id=venta_id, foto_referencia="foto2.jpg", datos_extraidos=datos
    )
    repo.guardar(t)
    resultado = repo.buscar_por_venta_id(venta_id)
    assert resultado is not None
    d = resultado.datos_extraidos
    assert d is not None
    assert d.nombre_cliente == "Juan"
    assert d.destinos == ("Cartagena", "Santa Marta")
    assert d.valor_venta == Dinero("500000")
    assert d.confianza == Decimal("0.95")
    assert d.fecha_salida == datetime.datetime(2026, 8, 1, 9, 0)
