"""Tests del tipo SQLAlchemy que mapea Numeric <-> Dinero."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.sqlite import dialect as _dialect_sqlite
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from garay.dominio.comun.dinero import Dinero
from garay.infraestructura.persistencia.tipos import TipoDinero

_DIALECT = _dialect_sqlite()


class TestConversion:
    def test_bind_devuelve_el_monto_decimal(self) -> None:
        assert TipoDinero().process_bind_param(Dinero("1000.50"), _DIALECT) == Decimal("1000.50")

    def test_result_reconstruye_dinero(self) -> None:
        assert TipoDinero().process_result_value(Decimal("1000.50"), _DIALECT) == Dinero("1000.50")

    def test_none_ida_y_vuelta(self) -> None:
        tipo = TipoDinero()
        assert tipo.process_bind_param(None, _DIALECT) is None
        assert tipo.process_result_value(None, _DIALECT) is None

    def test_moneda_configurable(self) -> None:
        reconstruido = TipoDinero("USD").process_result_value(Decimal("10"), _DIALECT)
        assert reconstruido == Dinero("10", "USD")


class _BasePrueba(DeclarativeBase):
    """Base aislada para no contaminar el metadata de la app."""


class _FilaConDinero(_BasePrueba):
    __tablename__ = "prueba_dinero"

    id: Mapped[int] = mapped_column(primary_key=True)
    importe: Mapped[Dinero] = mapped_column(TipoDinero())


class TestPersistenciaReal:
    @pytest.fixture
    def sesion(self) -> Iterator[Session]:
        engine = create_engine("sqlite://")
        _BasePrueba.metadata.create_all(engine)
        with Session(engine) as sesion:
            yield sesion

    def test_persiste_y_recupera_dinero(self, sesion: Session) -> None:
        sesion.add(_FilaConDinero(id=1, importe=Dinero(1000)))
        sesion.commit()
        sesion.expunge_all()

        recuperada = sesion.scalar(select(_FilaConDinero).where(_FilaConDinero.id == 1))
        assert recuperada is not None
        assert recuperada.importe == Dinero(1000)
