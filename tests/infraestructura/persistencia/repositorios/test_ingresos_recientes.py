"""Tests for SQLAIngresoRepository.listar_recientes — TDD RED phase."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Ingreso
from garay.infraestructura.persistencia.repositorios.ingresos import SQLAIngresoRepository

_UTC = datetime.UTC


def _make_ingreso(
    *,
    referencia: str = "MSG-001",
    clasificado: bool = False,
    fecha_recibido: datetime.datetime | None = None,
) -> Ingreso:
    now = fecha_recibido or datetime.datetime.now(_UTC)
    return Ingreso(
        id=uuid.uuid4(),
        banco="Bancolombia",
        monto=Dinero("500000"),
        fecha=now.date(),
        referencia=referencia,
        remitente="Juan Perez",
        clasificado=clasificado,
        fecha_recibido=fecha_recibido,
    )


def test_listar_recientes_retorna_solo_los_de_los_ultimos_n_minutos(
    sf: sessionmaker[Session],
) -> None:
    repo = SQLAIngresoRepository(sf)
    now = datetime.datetime.now(_UTC)

    reciente = _make_ingreso(referencia="MSG-A", fecha_recibido=now - datetime.timedelta(minutes=3))
    viejo = _make_ingreso(referencia="MSG-B", fecha_recibido=now - datetime.timedelta(minutes=10))

    repo.guardar(reciente)
    repo.guardar(viejo)

    resultado = repo.listar_recientes(5)

    ids = {r.id for r in resultado}
    assert reciente.id in ids
    assert viejo.id not in ids


def test_listar_recientes_lista_vacia_cuando_no_hay_ingresos_recientes(
    sf: sessionmaker[Session],
) -> None:
    repo = SQLAIngresoRepository(sf)
    now = datetime.datetime.now(_UTC)

    viejo = _make_ingreso(referencia="MSG-X", fecha_recibido=now - datetime.timedelta(minutes=30))
    repo.guardar(viejo)

    resultado = repo.listar_recientes(5)
    assert resultado == []


def test_listar_recientes_ingreso_sin_fecha_recibido_no_aparece(
    sf: sessionmaker[Session],
) -> None:
    """Ingresos without fecha_recibido (legacy) must NOT appear in recent results."""
    repo = SQLAIngresoRepository(sf)

    sin_hora = _make_ingreso(referencia="MSG-LEGACY", fecha_recibido=None)
    repo.guardar(sin_hora)

    resultado = repo.listar_recientes(5)
    assert resultado == []


def test_listar_recientes_en_limite_exacto_incluido(
    sf: sessionmaker[Session],
) -> None:
    """An ingreso within the boundary window is included; just outside is not."""
    repo = SQLAIngresoRepository(sf)
    now = datetime.datetime.now(_UTC)

    # 4 min 50 sec ago — comfortably inside the 5-minute window
    dentro = _make_ingreso(
        referencia="MSG-DENTRO",
        fecha_recibido=now - datetime.timedelta(minutes=4, seconds=50),
    )
    # 5 min 10 sec ago — comfortably outside the 5-minute window
    fuera = _make_ingreso(
        referencia="MSG-FUERA",
        fecha_recibido=now - datetime.timedelta(minutes=5, seconds=10),
    )
    repo.guardar(dentro)
    repo.guardar(fuera)

    resultado = repo.listar_recientes(5)
    ids = {r.id for r in resultado}
    assert dentro.id in ids
    assert fuera.id not in ids
