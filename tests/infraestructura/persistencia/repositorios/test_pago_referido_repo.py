"""Tests for task 3.4: SQLAPagoReferidoRepository."""

from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.liquidaciones.entidades import PagoReferido
from garay.infraestructura.persistencia import modelos  # noqa: F401
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.modelos import ClienteModel, VentaModel
from garay.infraestructura.persistencia.repositorios.pago_referido import (
    SQLAPagoReferidoRepository,
)


@pytest.fixture()
def sf() -> sessionmaker[Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _make_venta_row(sf: sessionmaker[Session]) -> uuid.UUID:
    """Insert minimal venta row for FK constraint."""
    from garay.dominio.comun.dinero import Dinero
    from garay.dominio.comun.tipos import TipoCliente
    from garay.dominio.ventas.entidades import Venta
    from garay.dominio.ventas.valor_objetos import Participantes
    from garay.infraestructura.persistencia.repositorios.ventas import SQLAVentaRepository

    cliente_id = uuid.uuid4()
    with sf.begin() as s:
        s.add(ClienteModel(id=cliente_id, nombre="Test", tipo="EXTERNO"))
    venta_id = uuid.uuid4()
    SQLAVentaRepository(sf).guardar(
        Venta(
            id=venta_id,
            valor_venta=Dinero(500_000),
            neto=Dinero(400_000),
            servicio_ids=[],
            cliente_id=cliente_id,
            tipo_cliente=TipoCliente.EXTERNO,
            fecha=datetime.date(2026, 10, 1),
            participantes=Participantes(),
        )
    )
    return venta_id


def _make_pago(
    venta_id: uuid.UUID,
    referido_alias: str = "taxi",
    monto: int = 18_000,
) -> PagoReferido:
    return PagoReferido(
        id=uuid.uuid4(),
        venta_id=venta_id,
        referido_alias=referido_alias,
        monto=Dinero(monto),
        fecha_pago=datetime.datetime(2026, 10, 15, 12, 0, tzinfo=datetime.timezone.utc),
        registrado_por_telegram_id=5870211102,
        registrado_por_nombre="Ryan",
    )


class TestSQLAPagoReferidoRepository:
    def test_guardar_y_listar(self, sf: sessionmaker[Session]) -> None:
        """Task 3.4: guardar then listar_por_referido returns the pago."""
        venta_id = _make_venta_row(sf)
        repo = SQLAPagoReferidoRepository(sf)
        pago = _make_pago(venta_id, "taxi")
        repo.guardar(pago)
        results = repo.listar_por_referido("taxi")
        assert len(results) == 1
        assert results[0].referido_alias == "taxi"
        assert results[0].monto == Dinero(18_000)

    def test_listar_por_venta(self, sf: sessionmaker[Session]) -> None:
        """Task 3.4: listar_por_venta returns pagos for that venta."""
        venta_id = _make_venta_row(sf)
        repo = SQLAPagoReferidoRepository(sf)
        pago = _make_pago(venta_id, "taxi")
        repo.guardar(pago)
        results = repo.listar_por_venta(venta_id)
        assert len(results) == 1
        assert results[0].venta_id == venta_id

    def test_buscar_solapados_detecta_solapamiento(self, sf: sessionmaker[Session]) -> None:
        """Task 3.4: overlap detection returns matching pago."""
        venta_id = _make_venta_row(sf)
        repo = SQLAPagoReferidoRepository(sf)
        pago = _make_pago(venta_id, "taxi")
        repo.guardar(pago)
        # The pago has fecha_pago=2026-10-15; buscar_solapados uses date range
        from datetime import date
        overlapping = repo.buscar_solapados(
            "taxi",
            date(2026, 10, 1),
            date(2026, 10, 31),
        )
        assert len(overlapping) == 1

    def test_buscar_solapados_alias_diferente_no_solapa(
        self, sf: sessionmaker[Session]
    ) -> None:
        """Task 3.4: different alias returns empty list."""
        venta_id = _make_venta_row(sf)
        repo = SQLAPagoReferidoRepository(sf)
        pago = _make_pago(venta_id, "taxi")
        repo.guardar(pago)
        from datetime import date
        result = repo.buscar_solapados("moto", date(2026, 10, 1), date(2026, 10, 31))
        assert result == []

    def test_eliminar_borra_el_registro(self, sf: sessionmaker[Session]) -> None:
        """Task 3.4: eliminar removes the row."""
        venta_id = _make_venta_row(sf)
        repo = SQLAPagoReferidoRepository(sf)
        pago = _make_pago(venta_id, "taxi")
        repo.guardar(pago)
        repo.eliminar(pago.id)
        results = repo.listar_por_referido("taxi")
        assert results == []
