from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.reportes.waterfall_ventas import WaterfallVentasService
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import EstadoVenta, TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

_SNAP = SnapshotReglas(
    TipoCliente.INTERNO, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")
)


def _venta(vid: uuid.UUID, valor: int, neto: int, canal: str = "Hotel") -> Venta:
    return Venta(
        id=vid,
        valor_venta=Dinero(valor),
        neto=Dinero(neto),
        servicio_ids=[],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.INTERNO,
        fecha=datetime.date(2026, 7, 5),
        participantes=Participantes(),
        estado=EstadoVenta.PROCESADA,
        canal_origen=canal,
    )


def _comision(vid: uuid.UUID, agencia: int) -> ComisionRegistrada:
    desglose = DesgloseComision(
        vendedor=Dinero(0),
        cerrador=Dinero(0),
        punto_de_venta=Dinero(0),
        referido=Dinero(0),
        agencia=Dinero(agencia),
        snapshot=_SNAP,
    )
    return ComisionRegistrada(venta_id=vid, desglose=desglose, fecha=datetime.date(2026, 7, 5))


def _svc(ventas: list[Venta], comisiones: list[ComisionRegistrada]) -> WaterfallVentasService:
    vr = MagicMock()
    vr.listar_por_periodo.return_value = ventas
    cr = MagicMock()
    cr.listar_por_venta_ids.return_value = comisiones
    return WaterfallVentasService(vr, cr)


def test_cascada() -> None:
    v1 = uuid.uuid4()
    svc = _svc([_venta(v1, 880000, 660000)], [_comision(v1, 132000)])
    r = svc.ejecutar(7, 2026)
    assert r.valor_bruto == Dinero(880000)
    assert r.costo_neto == Dinero(660000)
    assert r.margen == Dinero(220000)
    assert r.ganancia_agencia == Dinero(132000)
    assert r.comisiones == Dinero(88000)  # margen - agencia


def test_sin_ventas_da_cero() -> None:
    svc = _svc([], [])
    r = svc.ejecutar(7, 2026)
    assert r.valor_bruto == Dinero(0)
    assert r.margen == Dinero(0)
    assert r.ganancia_agencia == Dinero(0)
