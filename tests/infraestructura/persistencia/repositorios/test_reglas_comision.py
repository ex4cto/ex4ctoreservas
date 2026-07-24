from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.tipos import TipoCliente
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
