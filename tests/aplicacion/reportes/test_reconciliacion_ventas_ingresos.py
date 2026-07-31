from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.reportes.reconciliacion_ventas_ingresos import (
    ReconciliacionVentasIngresosService,
)
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import EstadoVenta, TipoCliente
from garay.dominio.conciliacion.entidades import Ingreso
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

_SNAP = SnapshotReglas(
    TipoCliente.INTERNO, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")
)


def _venta(vid: uuid.UUID) -> Venta:
    return Venta(
        id=vid, valor_venta=Dinero(100000), neto=Dinero(60000), servicio_ids=[],
        cliente_id=uuid.uuid4(), tipo_cliente=TipoCliente.INTERNO,
        fecha=datetime.date(2026, 7, 5), participantes=Participantes(),
        estado=EstadoVenta.PROCESADA, canal_origen="Hotel",
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


def _ingreso(monto: int, ref: str) -> Ingreso:
    return Ingreso(
        id=uuid.uuid4(), banco="Nequi", monto=Dinero(monto),
        fecha=datetime.date(2026, 7, 5), referencia=ref,
    )


def _svc(
    ventas: list[Venta], comisiones: list[ComisionRegistrada], ingresos: list[Ingreso]
) -> ReconciliacionVentasIngresosService:
    vr = MagicMock()
    vr.listar_por_periodo.return_value = ventas
    cr = MagicMock()
    cr.listar_por_venta_ids.return_value = comisiones
    ir = MagicMock()
    ir.listar_por_periodo.return_value = ingresos
    return ReconciliacionVentasIngresosService(vr, cr, ir)


def test_reconciliacion() -> None:
    v1 = uuid.uuid4()
    svc = _svc(
        [_venta(v1)],
        [_com(v1, 6800000)],
        [_ingreso(6000000, "R1"), _ingreso(750000, "R2")],
    )
    r = svc.ejecutar(7, 2026)
    assert r.total_agencia_esperada == Dinero(6800000)
    assert r.total_ingresos_banco == Dinero(6750000)
    assert r.diferencia == Dinero(-50000)  # banco - agencia
    # desviacion = -50000 / 6800000 * 100 ~ -0.74%
    assert round(r.porcentaje_desviacion, 2) == Decimal("-0.74")


def test_sin_agencia_desviacion_cero() -> None:
    svc = _svc([], [], [_ingreso(100000, "R1")])
    r = svc.ejecutar(7, 2026)
    assert r.porcentaje_desviacion == Decimal("0")
