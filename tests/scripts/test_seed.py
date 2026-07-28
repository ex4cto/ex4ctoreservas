"""Tests for the seed script — uses SQLite in-memory for speed and isolation."""

from __future__ import annotations

import sqlalchemy as sa
from scripts.seed import (
    seed_freelancers,
    seed_puntos_de_venta,
    seed_reglas_comision,
    seed_servicios,
)
from sqlalchemy.orm import sessionmaker

from garay.infraestructura.persistencia import modelos  # noqa: F401 — registers all ORM models
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.modelos import (
    FreelancerModel,
    PuntoDeVentaModel,
    ReglasComisionModel,
    ServicioModel,
)


def _make_session_factory() -> sessionmaker:  # type: ignore[type-arg]
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_seed_completo_sqlite() -> None:
    """Seed populates all tables with the expected row counts."""
    sf = _make_session_factory()

    with sf.begin() as session:
        seed_servicios(session)
        seed_puntos_de_venta(session)
        seed_reglas_comision(session)
        seed_freelancers(session)

    with sf.begin() as session:
        assert (
            session.execute(sa.select(sa.func.count()).select_from(ServicioModel)).scalar() == 137
        )
        assert (
            session.execute(sa.select(sa.func.count()).select_from(PuntoDeVentaModel)).scalar() == 4
        )
        assert (
            session.execute(sa.select(sa.func.count()).select_from(ReglasComisionModel)).scalar()
            == 3
        )
        assert (
            session.execute(sa.select(sa.func.count()).select_from(FreelancerModel)).scalar() == 8
        )


def test_seed_idempotente_sqlite() -> None:
    """Running the seed twice does not duplicate any records."""
    sf = _make_session_factory()

    for _ in range(2):
        with sf.begin() as session:
            seed_servicios(session)
            seed_puntos_de_venta(session)
            seed_reglas_comision(session)
            seed_freelancers(session)

    with sf.begin() as session:
        assert (
            session.execute(sa.select(sa.func.count()).select_from(ServicioModel)).scalar() == 137
        )
        assert (
            session.execute(sa.select(sa.func.count()).select_from(PuntoDeVentaModel)).scalar() == 4
        )
        assert (
            session.execute(sa.select(sa.func.count()).select_from(ReglasComisionModel)).scalar()
            == 3
        )
        assert (
            session.execute(sa.select(sa.func.count()).select_from(FreelancerModel)).scalar() == 8
        )


def test_seed_servicios_numero_unico() -> None:
    """Each service has a unique numero — the unique constraint holds."""
    sf = _make_session_factory()
    with sf.begin() as session:
        seed_servicios(session)

    with sf.begin() as session:
        numeros = session.execute(sa.select(ServicioModel.numero)).scalars().all()
    assert len(numeros) == len(set(numeros)), "Duplicate service numbers found"


def test_seed_puntos_porcentaje_capa() -> None:
    """Crespo has 20% cap, the rest have 0%."""
    sf = _make_session_factory()
    with sf.begin() as session:
        seed_puntos_de_venta(session)

    with sf.begin() as session:
        rows = session.execute(sa.select(PuntoDeVentaModel)).scalars().all()

    crespo = next(r for r in rows if r.nombre == "Crespo")
    others = [r for r in rows if r.nombre != "Crespo"]

    assert float(crespo.porcentaje_capa) == 20.0
    for r in others:
        assert float(r.porcentaje_capa) == 0.0


def test_seed_reglas_tipo_cliente_valores() -> None:
    """Commission rules store the correct string values for tipo_cliente."""
    from garay.dominio.comun.tipos import TipoCliente

    sf = _make_session_factory()
    with sf.begin() as session:
        seed_reglas_comision(session)

    with sf.begin() as session:
        rows = session.execute(sa.select(ReglasComisionModel)).scalars().all()

    tipos = {r.tipo_cliente for r in rows}
    expected = {TipoCliente.INTERNO.value, TipoCliente.EXTERNO.value, TipoCliente.DIGITAL.value}
    assert tipos == expected


def test_seed_freelancers_activos() -> None:
    """All seeded freelancers start active with no telegram_user_id."""
    sf = _make_session_factory()
    with sf.begin() as session:
        seed_freelancers(session)

    with sf.begin() as session:
        rows = session.execute(sa.select(FreelancerModel)).scalars().all()

    assert all(r.activo for r in rows)
    assert all(r.telegram_user_id is None for r in rows)
