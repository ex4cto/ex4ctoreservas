from __future__ import annotations

import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.tipos import TipoCliente
from garay.infraestructura.persistencia.modelos import ReglasComisionModel
from garay.infraestructura.persistencia.repositorios.reglas_comision import (
    SQLAReglasComisionRepository,
)


def test_guardar_y_buscar_por_tipo_cliente(sf: sessionmaker[Session]) -> None:
    repo = SQLAReglasComisionRepository(sf)
    r = ReglasComision(
        id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("20.00"),
        porcentaje_cerrador=Decimal("10.00"),
        porcentaje_referido_maximo=Decimal("5.00"),
    )
    repo.guardar(r)
    resultado = repo.buscar_por_tipo_cliente(TipoCliente.EXTERNO)
    assert resultado is not None
    assert resultado.tipo_cliente == TipoCliente.EXTERNO
    assert resultado.porcentaje_vendedor == Decimal("20.00")


def test_buscar_tipo_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAReglasComisionRepository(sf)
    assert repo.buscar_por_tipo_cliente(TipoCliente.DIGITAL) is None


class TestReglasComisionModelSchema:
    """WU-4: ReglasComisionModel schema — new columns + composite unique (JD-7)."""

    def test_schema_includes_punto_de_venta_nombre_column(self, sf: sessionmaker[Session]) -> None:
        with sf.begin() as session:
            result = session.execute(
                sa.text("SELECT punto_de_venta_nombre FROM reglas_comision LIMIT 0")
            )
            assert result is not None

    def test_schema_includes_numero_personas_column(self, sf: sessionmaker[Session]) -> None:
        with sf.begin() as session:
            result = session.execute(
                sa.text("SELECT numero_personas FROM reglas_comision LIMIT 0")
            )
            assert result is not None

    def test_composite_unique_allows_same_tipo_cliente_with_different_punto(
        self, sf: sessionmaker[Session]
    ) -> None:
        """Two rows with same tipo_cliente but different punto_de_venta_nombre must succeed."""
        with sf.begin() as session:
            session.add(
                ReglasComisionModel(
                    id=uuid.uuid4(),
                    tipo_cliente="EXTERNO",
                    porcentaje_vendedor=Decimal("30"),
                    porcentaje_cerrador=Decimal("30"),
                    porcentaje_referido_maximo=Decimal("10"),
                    punto_de_venta_nombre=None,
                    numero_personas=None,
                )
            )
            session.add(
                ReglasComisionModel(
                    id=uuid.uuid4(),
                    tipo_cliente="EXTERNO",
                    porcentaje_vendedor=Decimal("50"),
                    porcentaje_cerrador=Decimal("0"),
                    porcentaje_referido_maximo=Decimal("10"),
                    punto_de_venta_nombre="Crespo",
                    numero_personas=1,
                )
            )
        # If we get here, no unique violation was raised.
        with sf.begin() as session:
            count = session.execute(
                sa.select(sa.func.count()).select_from(ReglasComisionModel)
            ).scalar()
        assert count == 2

    def test_new_fields_round_trip_via_repo(self, sf: sessionmaker[Session]) -> None:
        """to_orm and to_domain map the 2 new columns correctly."""
        repo = SQLAReglasComisionRepository(sf)
        r = ReglasComision(
            id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
            porcentaje_vendedor=Decimal("50"),
            porcentaje_cerrador=Decimal("0"),
            porcentaje_referido_maximo=Decimal("10"),
            punto_de_venta_nombre="Crespo",
            numero_personas=1,
        )
        repo.guardar(r)
        # buscar_por_tipo_cliente only fetches global (IS NULL) rows — use direct query for Crespo.
        with sf.begin() as session:
            row = session.execute(
                sa.select(ReglasComisionModel).where(
                    ReglasComisionModel.punto_de_venta_nombre == "Crespo"
                )
            ).scalar_one()
        assert row.punto_de_venta_nombre == "Crespo"
        assert row.numero_personas == 1


class TestBuscarPorTipoClienteCoexistencia:
    """B1 co-existence: buscar_por_tipo_cliente must return only the global row
    even when Crespo-specific rows with the same tipo_cliente are present.

    This test was added as part of the CRITICAL-1 fix in Slice 1a — hardening
    buscar_por_tipo_cliente to filter IS NULL on punto_de_venta_nombre and
    numero_personas so that seeded Crespo rows never trigger MultipleResultsFound.
    """

    def test_buscar_por_tipo_cliente_returns_global_row_only_when_crespo_row_coexists(
        self, sf: sessionmaker[Session]
    ) -> None:
        """Insert global EXTERNO row + 2 Crespo EXTERNO rows; assert no exception
        and that the returned rule is the global one (punto_de_venta_nombre=None)."""
        repo = SQLAReglasComisionRepository(sf)

        global_id = uuid.uuid4()
        global_rule = ReglasComision(
            id=global_id,
            tipo_cliente=TipoCliente.EXTERNO,
            porcentaje_vendedor=Decimal("20.00"),
            porcentaje_cerrador=Decimal("10.00"),
            porcentaje_referido_maximo=Decimal("5.00"),
            punto_de_venta_nombre=None,
            numero_personas=None,
        )
        crespo_1p = ReglasComision(
            id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
            porcentaje_vendedor=Decimal("50.00"),
            porcentaje_cerrador=Decimal("0.00"),
            porcentaje_referido_maximo=Decimal("10.00"),
            punto_de_venta_nombre="Crespo",
            numero_personas=1,
        )
        crespo_2p = ReglasComision(
            id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
            porcentaje_vendedor=Decimal("30.00"),
            porcentaje_cerrador=Decimal("30.00"),
            porcentaje_referido_maximo=Decimal("10.00"),
            punto_de_venta_nombre="Crespo",
            numero_personas=2,
        )

        repo.guardar(global_rule)
        repo.guardar(crespo_1p)
        repo.guardar(crespo_2p)

        # Must NOT raise MultipleResultsFound; must return the global row.
        resultado = repo.buscar_por_tipo_cliente(TipoCliente.EXTERNO)

        assert resultado is not None
        assert resultado.id == global_id
        assert resultado.punto_de_venta_nombre is None
        assert resultado.numero_personas is None
