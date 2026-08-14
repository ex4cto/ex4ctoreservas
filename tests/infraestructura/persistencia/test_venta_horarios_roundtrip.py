"""Tests for Venta.horarios_por_servicio: entity field + VentaModel column + repo round-trip.

Phase 7 — TDD RED: tests are written first and fail until the implementation
adds the field to entidades.py, modelos.py, and ventas.py.
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
from garay.infraestructura.persistencia import modelos  # noqa: F401 — ensures all models registered
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.repositorios.ventas import (
    SQLAVentaRepository,
    to_domain,
    to_orm,
)


def _participantes() -> Participantes:
    return Participantes(
        vendedor_nombre="Vendedor",
        cerrador_nombre=None,
        punto_de_venta_id=None,
        referido_nombre=None,
        vendedor_id=None,
        cerrador_id=None,
    )


def _venta(horarios: dict[uuid.UUID, str] | None = None) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(100_000),
        neto=Dinero(80_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 12, 25),
        participantes=_participantes(),
        adultos=2,
        ninos=0,
        horarios_por_servicio=horarios,
    )


@pytest.fixture()
def sf():  # type: ignore[no-untyped-def]
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class TestVentaEntidad:
    """Venta dataclass carries horarios_por_servicio."""

    def test_default_horarios_es_none(self) -> None:
        """A Venta without horarios has horarios_por_servicio=None by default."""
        venta = _venta()
        assert venta.horarios_por_servicio is None

    def test_horarios_guardados_correctamente(self) -> None:
        """A Venta with horarios stores the dict unchanged."""
        uid = uuid.uuid4()
        venta = _venta(horarios={uid: "07:00"})
        assert venta.horarios_por_servicio == {uid: "07:00"}


class TestVentaModelColumn:
    """VentaModel has horarios_por_servicio JSON column."""

    def test_columna_existe_en_sqlite(self, sf: sessionmaker) -> None:  # type: ignore[type-arg]
        """VentaModel schema includes horarios_por_servicio column."""
        engine = sf.kw["bind"]
        inspector = sa.inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("ventas")}
        assert "horarios_por_servicio" in cols


class TestVentaHorariosRoundtrip:
    """to_orm / to_domain preserves horarios_por_servicio across serialization."""

    def test_roundtrip_con_horarios(self, sf: sessionmaker) -> None:  # type: ignore[type-arg]
        """Round-trip: {uuid_A: '07:00'} survives to_orm → to_domain."""
        uid = uuid.uuid4()
        venta = _venta(horarios={uid: "07:00"})

        modelo = to_orm(venta)
        with sf.begin() as session:
            session.add(modelo)

        with sf.begin() as session:
            modelo_leido = session.get(type(modelo), venta.id)
            assert modelo_leido is not None
            resultado = to_domain(modelo_leido)

        assert resultado.horarios_por_servicio == {uid: "07:00"}

    def test_roundtrip_none_permanece_none(self, sf: sessionmaker) -> None:  # type: ignore[type-arg]
        """Round-trip: None horarios_por_servicio survives as None."""
        venta = _venta()

        modelo = to_orm(venta)
        with sf.begin() as session:
            session.add(modelo)

        with sf.begin() as session:
            modelo_leido = session.get(type(modelo), venta.id)
            assert modelo_leido is not None
            resultado = to_domain(modelo_leido)

        assert resultado.horarios_por_servicio is None

    def test_roundtrip_multiples_tours(self, sf: sessionmaker) -> None:  # type: ignore[type-arg]
        """Round-trip: multiple uuid→horario pairs survive serialization."""
        uid1, uid2 = uuid.uuid4(), uuid.uuid4()
        venta = _venta(horarios={uid1: "07:00", uid2: "14:00"})

        modelo = to_orm(venta)
        with sf.begin() as session:
            session.add(modelo)

        with sf.begin() as session:
            modelo_leido = session.get(type(modelo), venta.id)
            assert modelo_leido is not None
            resultado = to_domain(modelo_leido)

        assert resultado.horarios_por_servicio == {uid1: "07:00", uid2: "14:00"}


class TestVentaRepositorioHorarios:
    """SQLAVentaRepository.guardar + buscar_por_id preserves horarios_por_servicio."""

    def test_repo_guardar_y_buscar_con_horarios(self, sf: sessionmaker) -> None:  # type: ignore[type-arg]
        """Repository round-trip via guardar + buscar_por_id preserves horarios."""
        uid = uuid.uuid4()
        venta = _venta(horarios={uid: "09:00"})
        repo = SQLAVentaRepository(sf)

        repo.guardar(venta)
        recuperada = repo.buscar_por_id(venta.id)

        assert recuperada is not None
        assert recuperada.horarios_por_servicio == {uid: "09:00"}
