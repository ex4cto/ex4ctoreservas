from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

from garay.aplicacion.reportes.ranking_canal import RankingCanalService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import EstadoVenta, TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes


def _venta(valor: int, neto: int, canal: str) -> Venta:
    return Venta(
        id=uuid.uuid4(),
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


def _svc(ventas: list[Venta]) -> RankingCanalService:
    vr = MagicMock()
    vr.listar_por_periodo.return_value = ventas
    return RankingCanalService(vr)


def test_agrupa_por_canal() -> None:
    svc = _svc([
        _venta(880000, 660000, "Hotel"),
        _venta(200000, 150000, "Hotel"),
        _venta(400000, 300000, "Externas"),
    ])
    r = svc.ejecutar(7, 2026)
    filas = {f.canal: f for f in r.filas}
    assert filas["Hotel"].cantidad == 2
    assert filas["Hotel"].valor == Dinero(1080000)
    assert filas["Hotel"].neto == Dinero(810000)
    assert filas["Hotel"].margen == Dinero(270000)
    assert filas["Externas"].cantidad == 1
    assert filas["Externas"].margen == Dinero(100000)


def test_canal_none_se_agrupa_como_sin_canal() -> None:
    svc = _svc([_venta(100000, 60000, None)])  # type: ignore[arg-type]
    r = svc.ejecutar(7, 2026)
    assert r.filas[0].canal == "Sin canal"
