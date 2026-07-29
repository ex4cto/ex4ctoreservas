"""Tests for SQLAEgresoRepository — RED phase."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.infraestructura.persistencia.repositorios.egresos import SQLAEgresoRepository


def _make_egreso(
    *,
    referencia: str | None = None,
    tipo: TipoEgreso = TipoEgreso.AUTOMATICO,
) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Compra en MOVISTAR PAGOSEPAYCO",
        monto=Dinero("69328.00"),
        fecha=datetime.date(2026, 7, 27),
        categoria="otro",
        tipo=tipo,
        referencia=referencia,
    )


def test_guardar_y_buscar_por_id(sf: sessionmaker[Session]) -> None:
    repo = SQLAEgresoRepository(sf)
    egreso = _make_egreso()

    repo.guardar(egreso)
    resultado = repo.buscar_por_id(egreso.id)

    assert resultado is not None
    assert resultado.id == egreso.id
    assert resultado.descripcion == "Compra en MOVISTAR PAGOSEPAYCO"
    assert resultado.monto == Dinero("69328.00")
    assert resultado.categoria == "otro"
    assert resultado.tipo == TipoEgreso.AUTOMATICO


def test_buscar_inexistente_devuelve_none(sf: sessionmaker[Session]) -> None:
    repo = SQLAEgresoRepository(sf)
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_existe_referencia_verdadero(sf: sessionmaker[Session]) -> None:
    repo = SQLAEgresoRepository(sf)
    egreso = _make_egreso(referencia="MSG-EGRESO-001")
    repo.guardar(egreso)

    assert repo.existe_referencia("MSG-EGRESO-001") is True


def test_existe_referencia_falso(sf: sessionmaker[Session]) -> None:
    repo = SQLAEgresoRepository(sf)
    assert repo.existe_referencia("MSG-INEXISTENTE") is False


def test_existe_referencia_con_referencia_none_no_falla(sf: sessionmaker[Session]) -> None:
    repo = SQLAEgresoRepository(sf)
    egreso = _make_egreso(referencia=None)
    repo.guardar(egreso)

    assert repo.existe_referencia("MSG-CUALQUIERA") is False
