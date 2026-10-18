"""End-to-end integration smoke test: EditarServicioService → SQLAAuditoriaEntidadesRepository.

Simulates an edit through the application service and verifies the audit row
is stored and retrievable via the real SQLA repo backed by in-memory SQLite.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from garay.aplicacion.servicios.editar_servicio import EditarServicioService
from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.persistencia import modelos  # noqa: F401
from garay.infraestructura.persistencia.base import Base
from garay.infraestructura.persistencia.repositorios.auditoria_entidades import (
    SQLAAuditoriaEntidadesRepository,
)
from garay.infraestructura.persistencia.repositorios.servicios import SQLAServicioRepository


@pytest.fixture()
def sf() -> sessionmaker[Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _make_servicio(sf: sessionmaker[Session]) -> Servicio:
    """Persist a fresh Servicio and return the domain object."""
    repo = SQLAServicioRepository(sf)
    s = Servicio(
        id=uuid.uuid4(),
        numero=1,
        nombre="TOUR PLAYA",
        activo=True,
        precio_neto_adulto=Decimal("50000"),
        precio_neto_nino=Decimal("25000"),
        precio_sugerido_adulto=Decimal("60000"),
        precio_sugerido_nino=Decimal("30000"),
        netos_por_horario={},
    )
    repo.guardar(s)
    return s


class TestIntegracionAuditoria:
    def test_editar_servicio_emite_fila_recuperable(
        self, sf: sessionmaker[Session]
    ) -> None:
        """Editing a service field creates exactly one audit row visible via listar()."""
        s = _make_servicio(sf)
        servicio_repo = SQLAServicioRepository(sf)
        auditoria_repo = SQLAAuditoriaEntidadesRepository(sf)
        service = EditarServicioService(servicios=servicio_repo, auditoria=auditoria_repo)

        service.editar(
            s.id,
            precio_neto_adulto=Decimal("70000"),
            por_telegram_id=5870211102,
            por_nombre="Ryan",
        )

        rows = auditoria_repo.listar()
        assert len(rows) == 1
        row = rows[0]
        assert row.campo == "precio_neto_adulto"
        # valor_anterior comes from str() of the Decimal returned by the DB
        # (may have trailing zeros e.g. "50000.00"); just check numeric equality.
        assert Decimal(row.valor_anterior) == Decimal("50000")
        assert Decimal(row.valor_nuevo) == Decimal("70000")
        assert row.entidad_tipo == "servicio"
        assert row.entidad_id == s.id
        assert row.realizada_por_telegram_id == 5870211102
        assert row.realizada_por_nombre == "Ryan"

    def test_editar_dos_campos_emite_dos_filas(
        self, sf: sessionmaker[Session]
    ) -> None:
        """Two changed fields yield two audit rows, one per field."""
        s = _make_servicio(sf)
        servicio_repo = SQLAServicioRepository(sf)
        auditoria_repo = SQLAAuditoriaEntidadesRepository(sf)
        service = EditarServicioService(servicios=servicio_repo, auditoria=auditoria_repo)

        service.editar(
            s.id,
            precio_neto_adulto=Decimal("70000"),
            activo=False,
            por_telegram_id=5870211102,
            por_nombre="Ryan",
        )

        rows = auditoria_repo.listar()
        assert len(rows) == 2
        campos = {r.campo for r in rows}
        assert campos == {"precio_neto_adulto", "activo"}

    def test_no_op_no_emite_filas(self, sf: sessionmaker[Session]) -> None:
        """An edit where nothing actually changes emits zero audit rows."""
        s = _make_servicio(sf)
        servicio_repo = SQLAServicioRepository(sf)
        auditoria_repo = SQLAAuditoriaEntidadesRepository(sf)
        service = EditarServicioService(servicios=servicio_repo, auditoria=auditoria_repo)

        # Load the actual persisted value to avoid Decimal precision mismatches
        # (DB returns e.g. Decimal("50000.00") for a stored 50000).
        persisted = servicio_repo.buscar_por_id(s.id)
        assert persisted is not None
        service.editar(
            s.id,
            precio_neto_adulto=persisted.precio_neto_adulto,
            por_telegram_id=5870211102,
            por_nombre="Ryan",
        )

        rows = auditoria_repo.listar()
        assert len(rows) == 0
