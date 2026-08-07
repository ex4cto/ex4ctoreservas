"""Tests for the seed script — uses SQLite in-memory for speed and isolation."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from scripts.seed import (
    seed_freelancers,
    seed_id,
    seed_puntos_de_venta,
    seed_reglas_comision,
    seed_servicios,
)
from sqlalchemy.orm import sessionmaker

from garay.dominio.comun.tipos import TipoCliente
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
    """Seed populates all tables with the expected row counts (3 global + 2 Crespo = 5)."""
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
            == 5
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
            == 5
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
    """Commission rules store the correct string values for tipo_cliente (global rows)."""
    sf = _make_session_factory()
    with sf.begin() as session:
        seed_reglas_comision(session)

    with sf.begin() as session:
        rows = session.execute(sa.select(ReglasComisionModel)).scalars().all()

    # Global rows still cover all three tipos (Crespo rows also carry EXTERNO sentinel).
    tipos = {r.tipo_cliente for r in rows if r.punto_de_venta_nombre is None}
    expected = {TipoCliente.INTERNO.value, TipoCliente.EXTERNO.value, TipoCliente.DIGITAL.value}
    assert tipos == expected


def test_seed_crespo_rows_exist() -> None:
    """Crespo commission rows are seeded with correct values (JD-4 / T-seed)."""
    sf = _make_session_factory()
    with sf.begin() as session:
        seed_reglas_comision(session)

    with sf.begin() as session:
        crespo_rows = (
            session.execute(
                sa.select(ReglasComisionModel).where(
                    ReglasComisionModel.punto_de_venta_nombre == "Crespo"
                )
            )
            .scalars()
            .all()
        )

    assert len(crespo_rows) == 2

    by_personas = {r.numero_personas: r for r in crespo_rows}
    assert set(by_personas.keys()) == {1, 2}

    row_1p = by_personas[1]
    assert row_1p.id == seed_id("regla:crespo:1p")
    assert row_1p.tipo_cliente == TipoCliente.EXTERNO.value  # sentinel
    assert Decimal(str(row_1p.porcentaje_vendedor)) == Decimal("50")
    assert Decimal(str(row_1p.porcentaje_cerrador)) == Decimal("0")
    assert Decimal(str(row_1p.porcentaje_referido_maximo)) == Decimal("10")

    row_2p = by_personas[2]
    assert row_2p.id == seed_id("regla:crespo:2p")
    assert row_2p.tipo_cliente == TipoCliente.EXTERNO.value  # sentinel
    assert Decimal(str(row_2p.porcentaje_vendedor)) == Decimal("30")
    assert Decimal(str(row_2p.porcentaje_cerrador)) == Decimal("30")
    assert Decimal(str(row_2p.porcentaje_referido_maximo)) == Decimal("10")


def test_seed_freelancers_activos() -> None:
    """All seeded freelancers start active with no telegram_user_id."""
    sf = _make_session_factory()
    with sf.begin() as session:
        seed_freelancers(session)

    with sf.begin() as session:
        rows = session.execute(sa.select(FreelancerModel)).scalars().all()

    assert all(r.activo for r in rows)
    assert all(r.telegram_user_id is None for r in rows)


def test_seed_playa_linda_tiene_precio_neto() -> None:
    """Service #124 (PLAYA LINDA) must have precio_neto_adulto == 55000 after bug-1B fix."""
    sf = _make_session_factory()
    with sf.begin() as session:
        seed_servicios(session)

    with sf.begin() as session:
        row = session.execute(
            sa.select(ServicioModel).where(ServicioModel.numero == 124)
        ).scalar_one()

    assert row.precio_neto_adulto == Decimal("55000"), (
        f"Expected 55000 for #124 PLAYA LINDA, got {row.precio_neto_adulto}"
    )
    # neto_nino intentionally stays null (no children price in the catalog)
    assert row.precio_neto_nino is None
