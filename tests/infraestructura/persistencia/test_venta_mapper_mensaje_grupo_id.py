"""Tests for mensaje_grupo_id field: Venta entity + VentaModel column + mapper round-trip.

TDD RED: tests are written first and fail until the implementation adds the field
to entidades.py, modelos.py, and the mapper in repositorios/ventas.py.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes
from garay.infraestructura.persistencia import modelos  # noqa: F401 — registers all models
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.repositorios.ventas import (
    SQLAVentaRepository,
    to_domain,
    to_orm,
)


def _participantes() -> Participantes:
    return Participantes(
        vendedor_nombre="Test",
        cerrador_nombre=None,
        punto_de_venta_id=None,
        referido_nombre=None,
        vendedor_id=None,
        cerrador_id=None,
    )


def _venta(mensaje_grupo_id: int | None = None) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(200_000),
        neto=Dinero(50_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 12, 31),
        participantes=_participantes(),
        adultos=1,
        ninos=0,
        mensaje_grupo_id=mensaje_grupo_id,
    )


@pytest.fixture()
def sf():  # type: ignore[no-untyped-def]
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class TestVentaEntidadMensajeGrupoId:
    """Venta dataclass carries mensaje_grupo_id."""

    def test_default_es_none(self) -> None:
        """A Venta without mensaje_grupo_id defaults to None."""
        venta = _venta()
        assert venta.mensaje_grupo_id is None

    def test_valor_no_nulo_guardado(self) -> None:
        """A Venta with mensaje_grupo_id stores the integer correctly."""
        venta = _venta(mensaje_grupo_id=999_001)
        assert venta.mensaje_grupo_id == 999_001


class TestVentaModelColumnaMensajeGrupoId:
    """VentaModel has mensaje_grupo_id column."""

    def test_columna_existe_en_sqlite(self, sf: sessionmaker) -> None:  # type: ignore[type-arg]
        engine = sf.kw["bind"]
        inspector = sa.inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("ventas")}
        assert "mensaje_grupo_id" in cols


class TestMapperRoundtripMensajeGrupoId:
    """to_orm / to_domain preserves mensaje_grupo_id."""

    def test_roundtrip_con_id_no_nulo(self, sf: sessionmaker) -> None:  # type: ignore[type-arg]
        """Round-trip: an integer mensaje_grupo_id survives to_orm → to_domain."""
        msg_id = 7_654_321
        venta = _venta(mensaje_grupo_id=msg_id)

        modelo = to_orm(venta)
        with sf.begin() as session:
            session.add(modelo)

        with sf.begin() as session:
            modelo_leido = session.get(type(modelo), venta.id)
            assert modelo_leido is not None
            resultado = to_domain(modelo_leido)

        assert resultado.mensaje_grupo_id == msg_id

    def test_roundtrip_none_permanece_none(self, sf: sessionmaker) -> None:  # type: ignore[type-arg]
        """Round-trip: None mensaje_grupo_id survives as None."""
        venta = _venta()

        modelo = to_orm(venta)
        with sf.begin() as session:
            session.add(modelo)

        with sf.begin() as session:
            modelo_leido = session.get(type(modelo), venta.id)
            assert modelo_leido is not None
            resultado = to_domain(modelo_leido)

        assert resultado.mensaje_grupo_id is None


class TestRepoRoundtripMensajeGrupoId:
    """SQLAVentaRepository.guardar + buscar_por_id preserves mensaje_grupo_id."""

    def test_repo_guarda_y_recupera_mensaje_grupo_id(
        self, sf: sessionmaker  # type: ignore[type-arg]
    ) -> None:
        """Repository round-trip via guardar + buscar_por_id preserves mensaje_grupo_id."""
        msg_id = 42_000_000
        venta = _venta(mensaje_grupo_id=msg_id)
        repo = SQLAVentaRepository(sf)

        repo.guardar(venta)
        recuperada = repo.buscar_por_id(venta.id)

        assert recuperada is not None
        assert recuperada.mensaje_grupo_id == msg_id
