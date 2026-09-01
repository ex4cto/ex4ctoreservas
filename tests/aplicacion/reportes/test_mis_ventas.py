"""Tests for MisVentasService — freelancer's own monthly sales + upcoming tours.

Option B: shows this month's realized tours plus ALL upcoming sold tours
(fecha > hoy, no upper bound). Commission counts only the role(s) the freelancer
actually played on each sale (fixes the previous vendedor+cerrador over-count).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.reportes.mis_ventas import MisVentasService
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

HOY = datetime.date(2026, 9, 15)
FID = uuid.uuid4()


def _snap() -> SnapshotReglas:
    return SnapshotReglas(
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("0"),
        porcentaje_cerrador=Decimal("0"),
        porcentaje_referido_maximo=Decimal("0"),
        porcentaje_capa_punto=Decimal("0"),
    )


def _venta(
    fecha: datetime.date,
    *,
    vendedor_id: uuid.UUID | None = None,
    cerrador_id: uuid.UUID | None = None,
    vendedor: str | None = "Ryan",
    cerrador: str | None = "Ryan",
    valor: int = 1_000_000,
) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(valor),
        neto=Dinero(valor // 2),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=fecha,
        participantes=Participantes(
            vendedor_nombre=vendedor,
            cerrador_nombre=cerrador,
            vendedor_id=vendedor_id,
            cerrador_id=cerrador_id,
        ),
    )


def _comision(venta_id: uuid.UUID, vendedor: int, cerrador: int) -> ComisionRegistrada:
    return ComisionRegistrada(
        venta_id=venta_id,
        desglose=DesgloseComision(
            vendedor=Dinero(vendedor),
            cerrador=Dinero(cerrador),
            punto_de_venta=Dinero(0),
            referido=Dinero(0),
            agencia=Dinero(0),
            snapshot=_snap(),
        ),
        fecha=HOY,
    )


def _service(ventas: list[Venta], comisiones: list[ComisionRegistrada]) -> MisVentasService:
    ventas_repo = MagicMock()
    ventas_repo.listar_por_freelancer_y_periodo.return_value = ventas
    comisiones_repo = MagicMock()
    comisiones_repo.listar_por_venta_ids.return_value = comisiones
    return MisVentasService(ventas=ventas_repo, comisiones=comisiones_repo)


def test_split_realizados_y_proximos_por_fecha() -> None:
    pasado = _venta(datetime.date(2026, 9, 10), vendedor_id=FID, cerrador_id=FID)
    futuro = _venta(datetime.date(2026, 9, 20), vendedor_id=FID, cerrador_id=FID)
    svc = _service(
        [pasado, futuro],
        [_comision(pasado.id, 50_000, 50_000), _comision(futuro.id, 60_000, 60_000)],
    )
    res = svc.ejecutar(FID, "Ryan", HOY)
    assert [linea.fecha for linea in res.realizados] == [datetime.date(2026, 9, 10)]
    assert [linea.fecha for linea in res.proximos] == [datetime.date(2026, 9, 20)]


def test_comision_solo_vendedor_no_suma_cerrador_ajeno() -> None:
    otro = uuid.uuid4()
    v = _venta(datetime.date(2026, 9, 10), vendedor_id=FID, cerrador_id=otro,
               vendedor="Ryan", cerrador="Otro")
    svc = _service([v], [_comision(v.id, 40_000, 30_000)])
    res = svc.ejecutar(FID, "Ryan", HOY)
    assert res.comision_total == Dinero(40_000)


def test_comision_ambos_roles_suma_los_dos() -> None:
    v = _venta(datetime.date(2026, 9, 10), vendedor_id=FID, cerrador_id=FID)
    svc = _service([v], [_comision(v.id, 40_000, 40_000)])
    res = svc.ejecutar(FID, "Ryan", HOY)
    assert res.comision_total == Dinero(80_000)


def test_comision_match_por_nombre_cuando_id_es_none() -> None:
    v = _venta(datetime.date(2026, 9, 10), vendedor_id=None, cerrador_id=None,
               vendedor="Ryan", cerrador="Otro")
    svc = _service([v], [_comision(v.id, 40_000, 30_000)])
    res = svc.ejecutar(FID, "Ryan", HOY)
    assert res.comision_total == Dinero(40_000)


def test_totales_y_conteo() -> None:
    v1 = _venta(datetime.date(2026, 9, 10), vendedor_id=FID, cerrador_id=FID, valor=1_000_000)
    v2 = _venta(datetime.date(2026, 9, 20), vendedor_id=FID, cerrador_id=FID, valor=500_000)
    svc = _service([v1, v2], [_comision(v1.id, 10_000, 10_000), _comision(v2.id, 5_000, 5_000)])
    res = svc.ejecutar(FID, "Ryan", HOY)
    assert res.total_ventas == 2
    assert res.valor_total == Dinero(1_500_000)
    assert res.comision_total == Dinero(30_000)


def test_vacio_devuelve_ceros() -> None:
    svc = _service([], [])
    res = svc.ejecutar(FID, "Ryan", HOY)
    assert res.total_ventas == 0
    assert res.realizados == ()
    assert res.proximos == ()
    assert res.comision_total == Dinero(0)


def test_consulta_usa_primer_dia_de_mes_y_date_max() -> None:
    """Option B: desde = first of month, hasta = date.max (no upper bound)."""
    ventas_repo = MagicMock()
    ventas_repo.listar_por_freelancer_y_periodo.return_value = []
    comisiones_repo = MagicMock()
    comisiones_repo.listar_por_venta_ids.return_value = []
    svc = MisVentasService(ventas=ventas_repo, comisiones=comisiones_repo)

    svc.ejecutar(FID, "Ryan", HOY)

    args = ventas_repo.listar_por_freelancer_y_periodo.call_args[0]
    assert args[2] == datetime.date(2026, 9, 1)
    assert args[3] == datetime.date.max
