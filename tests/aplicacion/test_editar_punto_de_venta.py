"""Unit tests for EditarPuntoDeVentaService — RED phase (TDD)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.puntos_venta.editar_punto import EditarPuntoDeVentaService
from garay.dominio.auditoria.entidades import RegistroAuditoria
from garay.dominio.puntos_venta.entidades import PuntoDeVenta


def _punto(**kwargs: object) -> PuntoDeVenta:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "nombre": "PLAYA LINDA",
        "porcentaje_capa": Decimal("10"),
    }
    defaults.update(kwargs)
    return PuntoDeVenta(**defaults)  # type: ignore[arg-type]

def _make_service(
    punto: PuntoDeVenta,
) -> tuple[EditarPuntoDeVentaService, MagicMock, MagicMock]:
    repo = MagicMock()
    repo.buscar_por_id.return_value = punto
    auditoria = MagicMock()
    return (
        EditarPuntoDeVentaService(puntos=repo, auditoria=auditoria),
        repo,
        auditoria,
    )

class TestCambiarPorcentajeCapa:
    def test_cambiar_porcentaje_capa_emite_un_registro(self) -> None:
        p = _punto()
        service, repo, auditoria = _make_service(p)
        service.editar(
            p.id,
            porcentaje_capa=Decimal("15"),
            por_telegram_id=9,
            por_nombre="Ryan",
        )
        assert auditoria.guardar.call_count == 1
        registro: RegistroAuditoria = auditoria.guardar.call_args[0][0]
        assert isinstance(registro, RegistroAuditoria)
        assert registro.campo == "porcentaje_capa"
        assert registro.valor_anterior == "10"
        assert registro.valor_nuevo == "15"
        assert registro.entidad_tipo == "punto_de_venta"
        assert registro.entidad_id == p.id
        assert registro.entidad_clave is None

    def test_repo_guardar_llamado_una_vez(self) -> None:
        p = _punto()
        service, repo, _ = _make_service(p)
        service.editar(p.id, porcentaje_capa=Decimal("15"), por_telegram_id=1, por_nombre="A")
        repo.guardar.assert_called_once()

class TestSinCambios:
    def test_mismo_porcentaje_no_emite_registros(self) -> None:
        p = _punto()
        service, _, auditoria = _make_service(p)
        service.editar(
            p.id,
            porcentaje_capa=p.porcentaje_capa,
            por_telegram_id=1,
            por_nombre="A",
        )
        auditoria.guardar.assert_not_called()

class TestMissingActor:
    def test_actor_none_lanza_antes_de_guardar(self) -> None:
        p = _punto()
        service, repo, auditoria = _make_service(p)
        with pytest.raises((ValueError, TypeError)):
            service.editar(
                p.id,
                porcentaje_capa=Decimal("15"),
                por_telegram_id=None,  # type: ignore[arg-type]
                por_nombre="A",
            )
        repo.guardar.assert_not_called()
        auditoria.guardar.assert_not_called()

class TestEntidadNoEncontrada:
    def test_punto_inexistente_lanza_value_error(self) -> None:
        repo = MagicMock()
        repo.buscar_por_id.return_value = None
        service = EditarPuntoDeVentaService(puntos=repo, auditoria=MagicMock())
        with pytest.raises(ValueError):
            service.editar(
                uuid.uuid4(),
                porcentaje_capa=Decimal("15"),
                por_telegram_id=1,
                por_nombre="A",
            )
