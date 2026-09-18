"""Tests for ServicioModel.netos_por_horario JSON round-trip.

TDD: RED phase — written before the ORM column and repo mapper implementation.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.repositorios.servicios import (
    SQLAServicioRepository,
)


@pytest.fixture()
def sf() -> sessionmaker[Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class TestNetosHorarioRoundTrip:
    """ServicioModel.netos_por_horario persists and reloads without float coercion."""

    def test_netos_round_trip_con_valor(self, sf: sessionmaker[Session]) -> None:
        """Saving {"08:00": Decimal("60000.00")} round-trips back as Decimal("60000.00")."""
        repo = SQLAServicioRepository(sf)
        s = Servicio(
            id=uuid.uuid4(),
            numero=130,
            nombre="City Tour Climatizado",
            netos_por_horario={"08:00": Decimal("60000.00")},
        )
        repo.guardar(s)
        resultado = repo.buscar_por_id(s.id)
        assert resultado is not None
        assert resultado.netos_por_horario == {"08:00": Decimal("60000.00")}
        assert isinstance(resultado.netos_por_horario["08:00"], Decimal)

    def test_netos_round_trip_vacio(self, sf: sessionmaker[Session]) -> None:
        """Empty dict round-trips correctly — no key error, no None."""
        repo = SQLAServicioRepository(sf)
        s = Servicio(
            id=uuid.uuid4(),
            numero=1,
            nombre="Tour Sin Neto Horario",
            netos_por_horario={},
        )
        repo.guardar(s)
        resultado = repo.buscar_por_id(s.id)
        assert resultado is not None
        assert resultado.netos_por_horario == {}

    def test_netos_multiples_horarios(self, sf: sessionmaker[Session]) -> None:
        """Multiple horario entries survive the JSON round-trip with exact Decimal fidelity."""
        repo = SQLAServicioRepository(sf)
        netos = {
            "08:00": Decimal("60000"),
            "13:00": Decimal("55000"),
        }
        s = Servicio(
            id=uuid.uuid4(),
            numero=2,
            nombre="City Tour Multi",
            netos_por_horario=netos,
        )
        repo.guardar(s)
        resultado = repo.buscar_por_id(s.id)
        assert resultado is not None
        assert resultado.netos_por_horario["08:00"] == Decimal("60000")
        assert resultado.netos_por_horario["13:00"] == Decimal("55000")
        # Must be Decimal, never float
        for v in resultado.netos_por_horario.values():
            assert isinstance(v, Decimal)

    def test_to_domain_popula_netos_por_horario(self, sf: sessionmaker[Session]) -> None:
        """to_domain() correctly maps netos_por_horario as dict[str, Decimal]."""
        repo = SQLAServicioRepository(sf)
        s = Servicio(
            id=uuid.uuid4(),
            numero=3,
            nombre="Tour To Domain",
            netos_por_horario={"08:00": Decimal("60000")},
        )
        repo.guardar(s)
        reloaded = repo.buscar_por_id(s.id)
        assert reloaded is not None
        # Must be Decimal, not str
        assert reloaded.netos_por_horario == {"08:00": Decimal("60000")}
        assert type(reloaded.netos_por_horario["08:00"]) is Decimal

    def test_default_cuando_no_se_pasa(self, sf: sessionmaker[Session]) -> None:
        """Servicio without netos_por_horario persists and reloads as empty dict."""
        repo = SQLAServicioRepository(sf)
        s = Servicio(id=uuid.uuid4(), numero=4, nombre="Tour Default")
        repo.guardar(s)
        resultado = repo.buscar_por_id(s.id)
        assert resultado is not None
        assert resultado.netos_por_horario == {}
