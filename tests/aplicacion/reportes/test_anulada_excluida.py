"""Integration test: anulada venta commission does NOT appear in ResumenVentasService.

Strategy chosen: ResumenVentasService.ejecutar() with real SQLite repos
(SQLAVentaRepository + SQLAComisionRegistradaRepository + SQLAFreelancerRepository).

Why the full service rather than repo-level assertions:
- listar_por_periodo already filters anulada=False at the repo level (Slice B1).
- Wiring the real service proves the chokepoint end-to-end without any mock:
  the anulada venta is absent from listar_por_periodo → its id is never in the
  venta_ids list → listar_por_venta_ids returns nothing for it → ganancia_agencia
  and total_valor exclude the anulada amounts.
- FreelancerRepository is wired with zero rows (listar_todos returns []) which is
  valid; the service falls back to snapshot names for bucketing and no exception
  is raised.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from garay.aplicacion.reportes.resumen_ventas import ResumenVentasService
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes
from garay.infraestructura.persistencia import modelos  # noqa: F401  (register all models)
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.modelos import ClienteModel
from garay.infraestructura.persistencia.repositorios.comisiones_registradas import (
    SQLAComisionRegistradaRepository,
)
from garay.infraestructura.persistencia.repositorios.freelancers import SQLAFreelancerRepository
from garay.infraestructura.persistencia.repositorios.ventas import SQLAVentaRepository

_MES = 8
_AÑO = 2026
_FECHA = datetime.date(_AÑO, _MES, 11)


@pytest.fixture()
def sf() -> sessionmaker[Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _make_cliente(sf: sessionmaker[Session]) -> uuid.UUID:
    cliente_id = uuid.uuid4()
    with sf.begin() as s:
        s.add(ClienteModel(id=cliente_id, nombre="Test Cliente", tipo="EXTERNO"))
    return cliente_id


def _make_snapshot() -> SnapshotReglas:
    return SnapshotReglas(
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("10"),
        porcentaje_cerrador=Decimal("5"),
        porcentaje_referido_maximo=Decimal("3"),
        porcentaje_capa_punto=Decimal("2"),
    )


def _make_comision(
    venta_id: uuid.UUID,
    *,
    vendedor: int,
    agencia: int,
) -> ComisionRegistrada:
    return ComisionRegistrada(
        venta_id=venta_id,
        desglose=DesgloseComision(
            vendedor=Dinero(vendedor),
            cerrador=Dinero(0),
            punto_de_venta=Dinero(0),
            referido=Dinero(0),
            agencia=Dinero(agencia),
            snapshot=_make_snapshot(),
        ),
        fecha=_FECHA,
    )


def test_anulada_comision_excluida_del_resumen(sf: sessionmaker[Session]) -> None:
    """ResumenVentasService.ejecutar does not include the anulada venta's amounts.

    Two ventas in the same period:
      - v_normal:  valor=500_000, commission agencia=200_000
      - v_anulada: valor=300_000, commission agencia=100_000  (soft-deleted)

    After ejecutar(mes, año):
      - total_ventas == 1         (only v_normal)
      - total_valor  == 500_000   (only v_normal's valor)
      - ganancia_agencia == 200_000 (only v_normal's commission)
    """
    cliente_id = _make_cliente(sf)

    venta_repo = SQLAVentaRepository(sf)
    comision_repo = SQLAComisionRegistradaRepository(sf)
    freelancer_repo = SQLAFreelancerRepository(sf)

    # Normal venta
    v_normal = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("500000"),
        neto=Dinero("300000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_FECHA,
        participantes=Participantes(vendedor_nombre="Carlos"),
    )
    venta_repo.guardar(v_normal)
    comision_repo.guardar(_make_comision(v_normal.id, vendedor=50_000, agencia=200_000))

    # Anulada venta — call .anular() so anulada=True is set via domain method
    v_anulada = Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero("300000"),
        neto=Dinero("200000"),
        servicio_ids=[],
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_FECHA,
        participantes=Participantes(vendedor_nombre="Carlos"),
    )
    v_anulada.anular()
    venta_repo.guardar(v_anulada)
    comision_repo.guardar(_make_comision(v_anulada.id, vendedor=30_000, agencia=100_000))

    service = ResumenVentasService(
        ventas=venta_repo,
        comisiones=comision_repo,
        freelancers=freelancer_repo,
    )
    resumen = service.ejecutar(mes=_MES, año=_AÑO)

    assert resumen.total_ventas == 1, (
        f"Expected 1 venta (normal only), got {resumen.total_ventas}"
    )
    assert resumen.total_valor == Dinero("500000"), (
        f"Expected total_valor=500000, got {resumen.total_valor}"
    )
    assert resumen.ganancia_agencia == Dinero("200000"), (
        f"Expected ganancia_agencia=200000 (normal only), got {resumen.ganancia_agencia}"
    )
