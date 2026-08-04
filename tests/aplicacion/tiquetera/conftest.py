from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from garay.infraestructura.persistencia import modelos  # noqa: F401
from garay.infraestructura.persistencia.base import Base


@pytest.fixture()
def sf() -> sessionmaker[Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
