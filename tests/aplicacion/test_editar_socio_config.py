"""Unit tests for EditarSocioConfigService — RED phase (TDD)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.socios.editar_socio import EditarSocioConfigService
from garay.dominio.auditoria.entidades import RegistroAuditoria
from garay.dominio.socios.entidades import SocioConfig


def _socio(**kwargs: object) -> SocioConfig:
    defaults: dict[str, object] = {
        "nombre": "garay",
        "porcentaje": Decimal("50"),
        "telegram_id": 1379898979,
    }
    defaults.update(kwargs)
    return SocioConfig(**defaults)  # type: ignore[arg-type]

def _make_service(
    socio: SocioConfig,
) -> tuple[EditarSocioConfigService, MagicMock, MagicMock]:
    repo = MagicMock()
    repo.buscar_por_nombre.return_value = socio
    auditoria = MagicMock()
    return (
        EditarSocioConfigService(socios=repo, auditoria=auditoria),
        repo,
        auditoria,
    )

class TestCambiarPorcentaje:
    def test_cambiar_porcentaje_emite_registro_con_clave(self) -> None:
        s = _socio()
        service, repo, auditoria = _make_service(s)
        service.editar(
            s.nombre,
            porcentaje=Decimal("60"),
            por_telegram_id=9,
            por_nombre="Ryan",
        )
        assert auditoria.guardar.call_count == 1
        registro: RegistroAuditoria = auditoria.guardar.call_args[0][0]
        assert isinstance(registro, RegistroAuditoria)
        assert registro.campo == "porcentaje"
        assert registro.valor_anterior == "50"
        assert registro.valor_nuevo == "60"
        assert registro.entidad_tipo == "socio_config"
        # socios_config uses entidad_clave not entidad_id
        assert registro.entidad_clave == "garay"
        assert registro.entidad_id is None

    def test_repo_guardar_llamado_una_vez(self) -> None:
        s = _socio()
        service, repo, _ = _make_service(s)
        service.editar(s.nombre, porcentaje=Decimal("60"), por_telegram_id=1, por_nombre="A")
        repo.guardar.assert_called_once()

class TestSinCambios:
    def test_mismo_porcentaje_no_emite_registros(self) -> None:
        s = _socio()
        service, _, auditoria = _make_service(s)
        service.editar(s.nombre, porcentaje=s.porcentaje, por_telegram_id=1, por_nombre="A")
        auditoria.guardar.assert_not_called()

class TestMissingActor:
    def test_actor_none_lanza_antes_de_guardar(self) -> None:
        s = _socio()
        service, repo, auditoria = _make_service(s)
        with pytest.raises((ValueError, TypeError)):
            service.editar(
                s.nombre,
                porcentaje=Decimal("60"),
                por_telegram_id=None,  # type: ignore[arg-type]
                por_nombre="A",
            )
        repo.guardar.assert_not_called()
        auditoria.guardar.assert_not_called()

class TestEntidadNoEncontrada:
    def test_socio_inexistente_lanza_value_error(self) -> None:
        repo = MagicMock()
        repo.buscar_por_nombre.return_value = None
        service = EditarSocioConfigService(socios=repo, auditoria=MagicMock())
        with pytest.raises(ValueError):
            service.editar(
                "ryan",
                porcentaje=Decimal("60"),
                por_telegram_id=1,
                por_nombre="A",
            )
