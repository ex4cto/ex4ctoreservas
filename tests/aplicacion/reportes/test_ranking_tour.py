from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.reportes.ranking_tour import RankingTourService
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import EstadoVenta, TipoCliente
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

_SNAP = SnapshotReglas(
    TipoCliente.INTERNO, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")
)


def _venta(vid: uuid.UUID, valor: int, neto: int, servicio_ids: list[uuid.UUID]) -> Venta:
    return Venta(
        id=vid,
        valor_venta=Dinero(valor),
        neto=Dinero(neto),
        servicio_ids=servicio_ids,
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.INTERNO,
        fecha=datetime.date(2026, 7, 5),
        participantes=Participantes(),
        estado=EstadoVenta.PROCESADA,
        canal_origen="Hotel",
    )


def _com(vid: uuid.UUID, agencia: int) -> ComisionRegistrada:
    return ComisionRegistrada(
        venta_id=vid,
        desglose=DesgloseComision(
            vendedor=Dinero(0), cerrador=Dinero(0), punto_de_venta=Dinero(0),
            referido=Dinero(0), agencia=Dinero(agencia), snapshot=_SNAP,
        ),
        fecha=datetime.date(2026, 7, 5),
    )


def _serv(sid: uuid.UUID, categoria: str) -> Servicio:
    return Servicio(id=sid, numero=1, nombre="Tour", categoria=categoria)


def _svc(
    ventas: list[Venta], comisiones: list[ComisionRegistrada], servicios: list[Servicio]
) -> RankingTourService:
    vr = MagicMock()
    vr.listar_por_periodo.return_value = ventas
    cr = MagicMock()
    cr.listar_por_venta_ids.return_value = comisiones
    sr = MagicMock()
    sr.listar.return_value = servicios
    return RankingTourService(vr, cr, sr)


def test_agrupa_por_familia() -> None:
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    v1, v2, v3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    svc = _svc(
        [_venta(v1, 800000, 600000, [s1]), _venta(v2, 200000, 150000, [s1]),
         _venta(v3, 400000, 300000, [s2])],
        [_com(v1, 80000), _com(v2, 20000), _com(v3, 40000)],
        [_serv(s1, "Islas del Rosario"), _serv(s2, "Playa Tranquila")],
    )
    r = svc.ejecutar(7, 2026)
    filas = {f.familia: f for f in r.filas}
    assert filas["Islas del Rosario"].vendidos == 2
    assert filas["Islas del Rosario"].valor == Dinero(1000000)
    assert filas["Islas del Rosario"].margen == Dinero(250000)
    assert filas["Islas del Rosario"].agencia == Dinero(100000)
    assert filas["Playa Tranquila"].vendidos == 1
    # ordenado por vendidos desc -> Islas primero
    assert r.filas[0].familia == "Islas del Rosario"


def test_venta_sin_servicio_es_sin_categoria() -> None:
    v1 = uuid.uuid4()
    svc = _svc([_venta(v1, 100000, 60000, [])], [_com(v1, 10000)], [])
    r = svc.ejecutar(7, 2026)
    assert r.filas[0].familia == "Sin categoria"
