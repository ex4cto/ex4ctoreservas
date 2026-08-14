from __future__ import annotations

from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from garay.infraestructura.persistencia import modelos  # noqa: F401
from garay.infraestructura.persistencia.base import Base

# Type alias for the 6-tuple catalog format consumed by FSMTiquetera.
CatalogoTuple = tuple[int, str, Decimal | None, Decimal | None, str, list[str]]

_DEFAULT_ENTRY: CatalogoTuple = (1, "Tour", Decimal("50"), Decimal("25"), "cat", [])


def catalogo_fsm(*overrides: dict[str, object]) -> list[CatalogoTuple]:
    """Build a list of 6-tuple catalog entries for FSMTiquetera tests.

    Each positional argument is a partial override dict for one entry.
    When no arguments are given, returns a single default entry:
      (1, "Tour", Decimal("50"), Decimal("25"), "cat", [])

    Keys: numero, nombre, neto_a, neto_n, categoria, horarios.

    Example:
        catalogo_fsm()
        # [(1, "Tour", Decimal("50"), Decimal("25"), "cat", [])]

        catalogo_fsm({"numero": 2, "horarios": ["07:00"]})
        # [(2, "Tour", Decimal("50"), Decimal("25"), "cat", ["07:00"])]
    """
    if not overrides:
        return [_DEFAULT_ENTRY]

    result: list[CatalogoTuple] = []
    for override in overrides:
        raw_numero = override.get("numero", _DEFAULT_ENTRY[0])
        numero: int = raw_numero if isinstance(raw_numero, int) else int(str(raw_numero))
        nombre = str(override.get("nombre", _DEFAULT_ENTRY[1]))
        neto_a_raw = override.get("neto_a", _DEFAULT_ENTRY[2])
        neto_n_raw = override.get("neto_n", _DEFAULT_ENTRY[3])
        neto_a: Decimal | None = Decimal(str(neto_a_raw)) if neto_a_raw is not None else None
        neto_n: Decimal | None = Decimal(str(neto_n_raw)) if neto_n_raw is not None else None
        categoria = str(override.get("categoria", _DEFAULT_ENTRY[4]))
        raw_horarios = override.get("horarios", _DEFAULT_ENTRY[5])
        horarios: list[str] = raw_horarios if isinstance(raw_horarios, list) else []
        result.append((numero, nombre, neto_a, neto_n, categoria, horarios))
    return result


@pytest.fixture()
def sf() -> sessionmaker[Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
