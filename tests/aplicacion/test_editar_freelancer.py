"""Unit tests for EditarFreelancerService — RED phase (TDD)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.freelancers.editar_freelancer import EditarFreelancerService
from garay.dominio.auditoria.entidades import RegistroAuditoria
from garay.dominio.freelancers.entidades import Freelancer


def _freelancer(**kwargs: object) -> Freelancer:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "nombre": "CARLOS",
        "activo": True,
        "es_admin": False,
    }
    defaults.update(kwargs)
    return Freelancer(**defaults)  # type: ignore[arg-type]


def _make_service(
    freelancer: Freelancer,
) -> tuple[EditarFreelancerService, MagicMock, MagicMock]:
    repo = MagicMock()
    repo.buscar_por_id.return_value = freelancer
    auditoria = MagicMock()
    return (
        EditarFreelancerService(freelancers=repo, auditoria=auditoria),
        repo,
        auditoria,
    )


class TestCampoUnico:
    def test_cambiar_nombre_emite_un_registro(self) -> None:
        f = _freelancer()
        service, repo, auditoria = _make_service(f)
        service.editar(f.id, nombre="CARLOS NUEVO", por_telegram_id=9, por_nombre="Ryan")
        assert auditoria.guardar.call_count == 1
        registro: RegistroAuditoria = auditoria.guardar.call_args[0][0]
        assert isinstance(registro, RegistroAuditoria)
        assert registro.campo == "nombre"
        assert registro.entidad_tipo == "freelancer"
        assert registro.entidad_id == f.id

    def test_cambiar_activo_emite_registro(self) -> None:
        f = _freelancer(activo=True)
        service, _, auditoria = _make_service(f)
        service.editar(f.id, activo=False, por_telegram_id=1, por_nombre="A")
        assert auditoria.guardar.call_count == 1
        registro = auditoria.guardar.call_args[0][0]
        assert registro.campo == "activo"
        assert registro.valor_anterior == "True"
        assert registro.valor_nuevo == "False"

    def test_cambiar_es_admin_emite_registro(self) -> None:
        f = _freelancer(es_admin=False)
        service, _, auditoria = _make_service(f)
        service.editar(f.id, es_admin=True, por_telegram_id=1, por_nombre="A")
        assert auditoria.guardar.call_count == 1
        registro = auditoria.guardar.call_args[0][0]
        assert registro.campo == "es_admin"


class TestSinCambios:
    def test_mismos_valores_no_emite_registros(self) -> None:
        f = _freelancer()
        service, _, auditoria = _make_service(f)
        service.editar(f.id, nombre=f.nombre, por_telegram_id=1, por_nombre="A")
        auditoria.guardar.assert_not_called()


class TestMissingActor:
    def test_actor_none_lanza_antes_de_guardar(self) -> None:
        f = _freelancer()
        service, repo, auditoria = _make_service(f)
        with pytest.raises((ValueError, TypeError)):
            service.editar(f.id, nombre="X", por_telegram_id=None, por_nombre="A")  # type: ignore[arg-type]
        repo.guardar.assert_not_called()
        auditoria.guardar.assert_not_called()


class TestEntidadNoEncontrada:
    def test_freelancer_inexistente_lanza_value_error(self) -> None:
        repo = MagicMock()
        repo.buscar_por_id.return_value = None
        service = EditarFreelancerService(freelancers=repo, auditoria=MagicMock())
        with pytest.raises(ValueError):
            service.editar(uuid.uuid4(), nombre="X", por_telegram_id=1, por_nombre="A")
