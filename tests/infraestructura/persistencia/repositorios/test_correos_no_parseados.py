"""Tests for SQLACorreoNoParseadoRepository — TDD RED phase."""

from __future__ import annotations

import datetime
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.conciliacion.entidades import CorreoNoParseado
from garay.infraestructura.persistencia.repositorios.correos_no_parseados import (
    SQLACorreoNoParseadoRepository,
)

_UTC = datetime.UTC


def _make_correo(
    *,
    referencia: str = "MSG-001",
    banco: str = "Nequi",
    procesado: bool = False,
    intentos: int = 0,
) -> CorreoNoParseado:
    return CorreoNoParseado(
        id=uuid.uuid4(),
        banco=banco,
        direccion="ingreso",
        referencia=referencia,
        asunto="Fwd: Transferencia recibida",
        correo_origen="nequi@notificaciones.com",
        cuerpo_texto="",
        cuerpo_html="<html>sin parse</html>",
        error_parseo="No se encontro monto",
        fecha_recibido=datetime.datetime(2026, 8, 1, 12, 0, 0, tzinfo=_UTC),
        procesado=procesado,
        intentos=intentos,
    )


def test_guardar_y_existe_referencia(sf: sessionmaker[Session]) -> None:
    repo = SQLACorreoNoParseadoRepository(sf)
    correo = _make_correo(referencia="MSG-UNIQUE")

    repo.guardar(correo)

    assert repo.existe_referencia("MSG-UNIQUE") is True


def test_existe_referencia_false_si_no_esta(sf: sessionmaker[Session]) -> None:
    repo = SQLACorreoNoParseadoRepository(sf)

    assert repo.existe_referencia("MSG-INEXISTENTE") is False


def test_listar_pendientes_excluye_procesados(sf: sessionmaker[Session]) -> None:
    repo = SQLACorreoNoParseadoRepository(sf)
    pendiente = _make_correo(referencia="MSG-PEND", procesado=False, intentos=0)
    procesado = _make_correo(referencia="MSG-PROC", procesado=True, intentos=0)
    repo.guardar(pendiente)
    repo.guardar(procesado)

    resultado = repo.listar_pendientes(max_intentos=5)

    ids = {c.id for c in resultado}
    assert pendiente.id in ids
    assert procesado.id not in ids


def test_listar_pendientes_excluye_los_que_superan_max_intentos(
    sf: sessionmaker[Session],
) -> None:
    repo = SQLACorreoNoParseadoRepository(sf)
    bajo = _make_correo(referencia="MSG-BAJO", procesado=False, intentos=2)
    alto = _make_correo(referencia="MSG-ALTO", procesado=False, intentos=5)
    repo.guardar(bajo)
    repo.guardar(alto)

    resultado = repo.listar_pendientes(max_intentos=5)

    ids = {c.id for c in resultado}
    assert bajo.id in ids
    assert alto.id not in ids


def test_marcar_procesado(sf: sessionmaker[Session]) -> None:
    repo = SQLACorreoNoParseadoRepository(sf)
    correo = _make_correo(referencia="MSG-MARCAR", procesado=False)
    repo.guardar(correo)

    repo.marcar_procesado(correo.id)

    pendientes = repo.listar_pendientes(max_intentos=99)
    ids = {c.id for c in pendientes}
    assert correo.id not in ids


def test_registrar_intento_fallido_incrementa_y_guarda_error(
    sf: sessionmaker[Session],
) -> None:
    repo = SQLACorreoNoParseadoRepository(sf)
    correo = _make_correo(referencia="MSG-FALLO", intentos=0)
    repo.guardar(correo)

    repo.registrar_intento_fallido(correo.id, "Timeout al parsear HTML")

    pendientes = repo.listar_pendientes(max_intentos=99)
    actualizado = next(c for c in pendientes if c.id == correo.id)
    assert actualizado.intentos == 1
    assert actualizado.error_ultimo == "Timeout al parsear HTML"


def test_unique_constraint_referencia_impide_duplicado(sf: sessionmaker[Session]) -> None:
    repo = SQLACorreoNoParseadoRepository(sf)
    correo1 = _make_correo(referencia="MSG-DUP")
    correo2 = _make_correo(referencia="MSG-DUP")

    repo.guardar(correo1)

    with pytest.raises(IntegrityError):
        repo.guardar(correo2)
