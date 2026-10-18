"""Unit tests for EditarServicioService — RED phase (TDD)."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.servicios.editar_servicio import EditarServicioService
from garay.dominio.auditoria.entidades import RegistroAuditoria
from garay.dominio.servicios.entidades import Servicio


def _servicio(**kwargs: object) -> Servicio:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "numero": 1,
        "nombre": "TOUR PLAYA",
        "activo": True,
        "precio_neto_adulto": Decimal("50000"),
        "precio_neto_nino": Decimal("25000"),
        "precio_sugerido_adulto": Decimal("60000"),
        "precio_sugerido_nino": Decimal("30000"),
        "netos_por_horario": {},
    }
    defaults.update(kwargs)
    return Servicio(**defaults)  # type: ignore[arg-type]


def _make_service(
    servicio: Servicio,
) -> tuple[EditarServicioService, MagicMock, MagicMock]:
    repo = MagicMock()
    repo.buscar_por_id.return_value = servicio
    auditoria = MagicMock()
    return EditarServicioService(servicios=repo, auditoria=auditoria), repo, auditoria


class TestCampoUnico:
    def test_un_campo_emite_exactamente_un_registro(self) -> None:
        s = _servicio()
        service, repo, auditoria = _make_service(s)
        service.editar(
            s.id,
            precio_neto_adulto=Decimal("60000"),
            por_telegram_id=9,
            por_nombre="Ryan",
        )
        assert auditoria.guardar.call_count == 1
        registro: RegistroAuditoria = auditoria.guardar.call_args[0][0]
        assert isinstance(registro, RegistroAuditoria)
        assert registro.campo == "precio_neto_adulto"
        assert registro.valor_anterior == "50000"
        assert registro.valor_nuevo == "60000"
        assert registro.entidad_tipo == "servicio"
        assert registro.entidad_id == s.id
        assert registro.realizada_por_telegram_id == 9
        assert registro.realizada_por_nombre == "Ryan"

    def test_repo_guardar_llamado_una_vez(self) -> None:
        s = _servicio()
        service, repo, _ = _make_service(s)
        service.editar(s.id, nombre="NUEVO TOUR", por_telegram_id=1, por_nombre="A")
        repo.guardar.assert_called_once()


class TestMultiplesCampos:
    def test_dos_campos_cambiados_emiten_dos_registros(self) -> None:
        s = _servicio()
        service, _, auditoria = _make_service(s)
        service.editar(
            s.id,
            precio_neto_adulto=Decimal("60000"),
            activo=False,
            por_telegram_id=9,
            por_nombre="Ryan",
        )
        assert auditoria.guardar.call_count == 2
        campos = {auditoria.guardar.call_args_list[i][0][0].campo for i in range(2)}
        assert campos == {"precio_neto_adulto", "activo"}


class TestSinCambios:
    def test_sin_cambios_no_emite_registros(self) -> None:
        s = _servicio()
        service, repo, auditoria = _make_service(s)
        # Pass the same values as current — no diff
        service.editar(
            s.id,
            precio_neto_adulto=s.precio_neto_adulto,
            por_telegram_id=9,
            por_nombre="Ryan",
        )
        auditoria.guardar.assert_not_called()
        # guardar still called once (entity always persisted)
        repo.guardar.assert_called_once()

    def test_noop_sin_kwargs_no_emite_registros(self) -> None:
        s = _servicio()
        service, _, auditoria = _make_service(s)
        service.editar(s.id, por_telegram_id=9, por_nombre="Ryan")
        auditoria.guardar.assert_not_called()


class TestMissingActor:
    def test_actor_none_lanza_antes_de_guardar(self) -> None:
        s = _servicio()
        service, repo, auditoria = _make_service(s)
        with pytest.raises((ValueError, TypeError)):
            service.editar(s.id, nombre="NUEVO", por_telegram_id=None, por_nombre="A")  # type: ignore[arg-type]
        repo.guardar.assert_not_called()
        auditoria.guardar.assert_not_called()


class TestCampoJson:
    def test_netos_por_horario_emite_json_canonico(self) -> None:
        s = _servicio(netos_por_horario={"08:00": Decimal("40000")})
        service, _, auditoria = _make_service(s)
        service.editar(
            s.id,
            netos_por_horario={"08:00": Decimal("40000"), "10:00": Decimal("45000")},
            por_telegram_id=1,
            por_nombre="A",
        )
        assert auditoria.guardar.call_count == 1
        registro = auditoria.guardar.call_args[0][0]
        assert registro.campo == "netos_por_horario"
        assert registro.valor_anterior == json.dumps(
            {"08:00": "40000"}, sort_keys=True, ensure_ascii=False
        )
        assert registro.valor_nuevo == json.dumps(
            {"08:00": "40000", "10:00": "45000"}, sort_keys=True, ensure_ascii=False
        )


class TestEntidadNoEncontrada:
    def test_servicio_inexistente_lanza_value_error(self) -> None:
        repo = MagicMock()
        repo.buscar_por_id.return_value = None
        service = EditarServicioService(servicios=repo, auditoria=MagicMock())
        with pytest.raises(ValueError):
            service.editar(uuid.uuid4(), nombre="X", por_telegram_id=1, por_nombre="A")
