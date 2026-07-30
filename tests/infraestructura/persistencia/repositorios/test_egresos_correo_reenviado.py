"""Tests for correo_origen/reenviado round-trip and listar_recientes
in SQLAEgresoRepository — RED phase."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.tipos import TipoEgreso
from garay.infraestructura.persistencia.repositorios.egresos import SQLAEgresoRepository

_UTC = datetime.UTC


def _make_egreso(
    *,
    referencia: str | None = None,
    tipo: TipoEgreso = TipoEgreso.AUTOMATICO,
    correo_origen: str | None = None,
    reenviado: bool = False,
    fecha_recibido: datetime.datetime | None = None,
) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Compra de prueba",
        monto=Dinero("50000"),
        fecha=datetime.date(2026, 7, 30),
        categoria="otro",
        tipo=tipo,
        referencia=referencia,
        correo_origen=correo_origen,
        reenviado=reenviado,
        fecha_recibido=fecha_recibido,
    )


def test_correo_origen_round_trip(sf: sessionmaker[Session]) -> None:
    repo = SQLAEgresoRepository(sf)
    egreso = _make_egreso(referencia="MSG-EA", correo_origen="alertas@bancolombia.com")
    repo.guardar(egreso)

    resultado = repo.buscar_por_id(egreso.id)

    assert resultado is not None
    assert resultado.correo_origen == "alertas@bancolombia.com"


def test_reenviado_true_round_trip(sf: sessionmaker[Session]) -> None:
    repo = SQLAEgresoRepository(sf)
    egreso = _make_egreso(referencia="MSG-EB", reenviado=True)
    repo.guardar(egreso)

    resultado = repo.buscar_por_id(egreso.id)

    assert resultado is not None
    assert resultado.reenviado is True


def test_correo_origen_none_round_trip(sf: sessionmaker[Session]) -> None:
    repo = SQLAEgresoRepository(sf)
    egreso = _make_egreso(referencia="MSG-EC")
    repo.guardar(egreso)

    resultado = repo.buscar_por_id(egreso.id)

    assert resultado is not None
    assert resultado.correo_origen is None


def test_reenviado_defaults_false(sf: sessionmaker[Session]) -> None:
    repo = SQLAEgresoRepository(sf)
    egreso = _make_egreso(referencia="MSG-ED")
    repo.guardar(egreso)

    resultado = repo.buscar_por_id(egreso.id)

    assert resultado is not None
    assert resultado.reenviado is False


def test_listar_recientes_retorna_solo_los_de_los_ultimos_n_minutos(
    sf: sessionmaker[Session],
) -> None:
    repo = SQLAEgresoRepository(sf)
    now = datetime.datetime.now(_UTC)

    reciente = _make_egreso(
        referencia="MSG-EX",
        fecha_recibido=now - datetime.timedelta(minutes=3),
    )
    viejo = _make_egreso(
        referencia="MSG-EY",
        fecha_recibido=now - datetime.timedelta(minutes=10),
    )

    repo.guardar(reciente)
    repo.guardar(viejo)

    resultado = repo.listar_recientes(5)

    ids = {e.id for e in resultado}
    assert reciente.id in ids
    assert viejo.id not in ids


def test_listar_recientes_sin_fecha_recibido_no_aparece(
    sf: sessionmaker[Session],
) -> None:
    repo = SQLAEgresoRepository(sf)
    egreso = _make_egreso(referencia="MSG-EZ", fecha_recibido=None)
    repo.guardar(egreso)

    resultado = repo.listar_recientes(5)
    assert resultado == []


def test_listar_recientes_vacio_si_no_hay_recientes(
    sf: sessionmaker[Session],
) -> None:
    repo = SQLAEgresoRepository(sf)
    now = datetime.datetime.now(_UTC)
    viejo = _make_egreso(
        referencia="MSG-EW",
        fecha_recibido=now - datetime.timedelta(minutes=30),
    )
    repo.guardar(viejo)

    resultado = repo.listar_recientes(5)
    assert resultado == []
