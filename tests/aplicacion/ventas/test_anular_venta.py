"""Tests for AnularVentaService — updated for audit-first ordering (B2 review)."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.ventas.anular_venta import AnularVentaService
from garay.aplicacion.ventas.comandos import AnularVentaComando
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada, VentaYaAnulada


def _make_venta(anulada: bool = False) -> MagicMock:
    venta = MagicMock()
    venta.id = uuid.uuid4()
    venta.anulada = anulada

    def _anular() -> None:
        if venta.anulada:
            raise VentaYaAnulada("La venta ya fue anulada.")
        venta.anulada = True

    venta.anular.side_effect = _anular
    return venta


_SENTINEL: MagicMock = MagicMock()  # module-level singleton avoids B008


def _make_repos(venta: MagicMock | None = _SENTINEL) -> tuple[MagicMock, MagicMock]:
    """Build repo mocks. Pass venta=None to simulate 'not found' in the repo."""
    resolved: MagicMock | None = _make_venta() if venta is _SENTINEL else venta
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = resolved
    auditoria_repo = MagicMock()
    return ventas_repo, auditoria_repo


class TestAnularVentaService:
    def test_success_marca_venta_anulada_y_guarda(self) -> None:
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = AnularVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        cmd = AnularVentaComando(
            venta_id=venta.id,
            motivo="Cancelacion por cliente",
            realizada_por_telegram_id=42,
            realizada_por_nombre="Admin",
        )
        service.ejecutar(cmd)

        venta.anular.assert_called_once()
        ventas_repo.guardar.assert_called_once_with(venta)
        auditoria_repo.guardar.assert_called_once()

    def test_success_audit_guardado_antes_que_venta(self) -> None:
        """auditoria.guardar must be called BEFORE ventas.guardar (audit-first invariant)."""
        venta = _make_venta()

        parent = MagicMock()
        parent.ventas = MagicMock()
        parent.ventas.buscar_por_id.return_value = venta
        parent.auditoria = MagicMock()

        service = AnularVentaService(ventas=parent.ventas, auditoria=parent.auditoria)

        cmd = AnularVentaComando(
            venta_id=venta.id,
            motivo="Orden de auditoria",
            realizada_por_telegram_id=1,
            realizada_por_nombre="Admin",
        )
        service.ejecutar(cmd)

        # Extract the order of guardar calls via the parent mock call list.
        guardar_calls = [c for c in parent.mock_calls if "guardar" in str(c)]
        assert len(guardar_calls) == 2
        # First guardar must be auditoria.guardar, not ventas.guardar.
        assert "auditoria.guardar" in str(guardar_calls[0])
        assert "ventas.guardar" in str(guardar_calls[1])

    def test_auditoria_guardar_raises_venta_never_persisted(self) -> None:
        """If auditoria.guardar raises, ventas.guardar must NOT be called."""
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        auditoria_repo.guardar.side_effect = RuntimeError("DB constraint")
        service = AnularVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        cmd = AnularVentaComando(
            venta_id=venta.id,
            motivo="Motivo valido",
            realizada_por_telegram_id=1,
            realizada_por_nombre=None,
        )
        with pytest.raises(RuntimeError, match="DB constraint"):
            service.ejecutar(cmd)

        ventas_repo.guardar.assert_not_called()

    def test_success_guarda_registro_auditoria_con_campos_correctos(self) -> None:
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = AnularVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        cmd = AnularVentaComando(
            venta_id=venta.id,
            motivo="  motivo con espacios  ",
            realizada_por_telegram_id=99,
            realizada_por_nombre="Propietario",
        )
        service.ejecutar(cmd)

        auditoria_repo.guardar.assert_called_once()
        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.accion == AccionAuditoria.ANULAR
        assert registro.motivo == "motivo con espacios"  # stripped
        assert registro.realizada_por_telegram_id == 99
        assert registro.realizada_por_nombre == "Propietario"
        assert registro.venta_id == venta.id
        assert isinstance(registro.realizada_at, datetime.datetime)
        assert registro.realizada_at.tzinfo is not None  # timezone-aware

    def test_success_realizada_por_nombre_none(self) -> None:
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = AnularVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        cmd = AnularVentaComando(
            venta_id=venta.id,
            motivo="Motivo valido",
            realizada_por_telegram_id=1,
            realizada_por_nombre=None,
        )
        service.ejecutar(cmd)

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.realizada_por_nombre is None

    def test_motivo_vacio_raises_motivo_requerido_y_no_guarda(self) -> None:
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = AnularVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        cmd = AnularVentaComando(
            venta_id=venta.id,
            motivo="   ",
            realizada_por_telegram_id=1,
            realizada_por_nombre="Admin",
        )
        with pytest.raises(MotivoRequerido):
            service.ejecutar(cmd)

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_motivo_cadena_vacia_raises_motivo_requerido(self) -> None:
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = AnularVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        cmd = AnularVentaComando(
            venta_id=venta.id,
            motivo="",
            realizada_por_telegram_id=1,
            realizada_por_nombre=None,
        )
        with pytest.raises(MotivoRequerido):
            service.ejecutar(cmd)

    def test_venta_no_encontrada_raises_venta_no_encontrada(self) -> None:
        ventas_repo, auditoria_repo = _make_repos(venta=None)
        service = AnularVentaService(ventas=ventas_repo, auditoria=auditoria_repo)
        venta_id = uuid.uuid4()

        cmd = AnularVentaComando(
            venta_id=venta_id,
            motivo="Motivo valido",
            realizada_por_telegram_id=1,
            realizada_por_nombre=None,
        )
        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(cmd)

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_venta_ya_anulada_propaga_venta_ya_anulada(self) -> None:
        """VentaYaAnulada is raised before either guardar is called."""
        venta = _make_venta(anulada=True)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = AnularVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        cmd = AnularVentaComando(
            venta_id=venta.id,
            motivo="Motivo",
            realizada_por_telegram_id=1,
            realizada_por_nombre=None,
        )
        with pytest.raises(VentaYaAnulada):
            service.ejecutar(cmd)

        # Neither guardar must have been called — the guard fires before any persistence.
        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()
