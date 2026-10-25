"""Unit tests for EditarReglasComisionService — RED phase (TDD)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.comisiones.editar_reglas import EditarReglasComisionService
from garay.dominio.auditoria.entidades import RegistroAuditoria
from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.tipos import TipoCliente


def _regla(**kwargs: object) -> ReglasComision:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "tipo_cliente": TipoCliente.INTERNO,
        "porcentaje_vendedor": Decimal("20"),
        "porcentaje_cerrador": Decimal("10"),
    }
    defaults.update(kwargs)
    return ReglasComision(**defaults)  # type: ignore[arg-type]

def _make_service(
    regla: ReglasComision,
) -> tuple[EditarReglasComisionService, MagicMock, MagicMock]:
    repo = MagicMock()
    repo.buscar_por_id.return_value = regla
    auditoria = MagicMock()
    return (
        EditarReglasComisionService(reglas=repo, auditoria=auditoria),
        repo,
        auditoria,
    )

class TestCampoUnico:
    def test_cambiar_porcentaje_vendedor_emite_registro(self) -> None:
        r = _regla()
        service, repo, auditoria = _make_service(r)
        service.editar(
            r.id,
            porcentaje_vendedor=Decimal("25"),
            por_telegram_id=9,
            por_nombre="Ryan",
        )
        assert auditoria.guardar.call_count == 1
        registro: RegistroAuditoria = auditoria.guardar.call_args[0][0]
        assert isinstance(registro, RegistroAuditoria)
        assert registro.campo == "porcentaje_vendedor"
        assert registro.valor_anterior == "20"
        assert registro.valor_nuevo == "25"
        assert registro.entidad_tipo == "regla_comision"
        assert registro.entidad_id == r.id

    def test_cambiar_porcentaje_cerrador(self) -> None:
        r = _regla()
        service, _, auditoria = _make_service(r)
        service.editar(r.id, porcentaje_cerrador=Decimal("15"), por_telegram_id=1, por_nombre="A")
        assert auditoria.guardar.call_count == 1
        registro = auditoria.guardar.call_args[0][0]
        assert registro.campo == "porcentaje_cerrador"


class TestMultiplesCampos:
    def test_dos_campos_emiten_dos_registros(self) -> None:
        r = _regla()
        service, _, auditoria = _make_service(r)
        service.editar(
            r.id,
            porcentaje_vendedor=Decimal("25"),
            porcentaje_cerrador=Decimal("15"),
            por_telegram_id=1,
            por_nombre="A",
        )
        assert auditoria.guardar.call_count == 2

class TestSinCambios:
    def test_mismos_valores_no_emite_registros(self) -> None:
        r = _regla()
        service, _, auditoria = _make_service(r)
        service.editar(
            r.id,
            porcentaje_vendedor=r.porcentaje_vendedor,
            por_telegram_id=1,
            por_nombre="A",
        )
        auditoria.guardar.assert_not_called()

class TestMissingActor:
    def test_actor_none_lanza_antes_de_guardar(self) -> None:
        r = _regla()
        service, repo, auditoria = _make_service(r)
        with pytest.raises((ValueError, TypeError)):
            service.editar(
                r.id,
                porcentaje_vendedor=Decimal("25"),
                por_telegram_id=None,  # type: ignore[arg-type]
                por_nombre="A",
            )
        repo.guardar.assert_not_called()
        auditoria.guardar.assert_not_called()

class TestEntidadNoEncontrada:
    def test_regla_inexistente_lanza_value_error(self) -> None:
        repo = MagicMock()
        repo.buscar_por_id.return_value = None
        service = EditarReglasComisionService(reglas=repo, auditoria=MagicMock())
        with pytest.raises(ValueError):
            service.editar(
                uuid.uuid4(),
                porcentaje_vendedor=Decimal("25"),
                por_telegram_id=1,
                por_nombre="A",
            )
