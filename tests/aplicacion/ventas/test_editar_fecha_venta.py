"""Tests for EditarFechaVentaService — Strict TDD (B3)."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.ventas.comandos import EditarFechaVentaComando
from garay.aplicacion.ventas.editar_fecha_venta import EditarFechaVentaService
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import MotivoRequerido, VentaNoEncontrada, VentaYaAnulada

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NUEVA_FECHA = datetime.datetime(2026, 9, 20, 10, 30)


def _make_venta(anulada: bool = False) -> MagicMock:
    venta = MagicMock()
    venta.id = uuid.uuid4()
    venta.fecha = datetime.date(2026, 8, 10)
    venta.anulada = anulada

    def _cambiar_fecha(nueva: datetime.datetime) -> None:
        if venta.anulada:
            raise VentaYaAnulada("Ya anulada.")
        venta.fecha = nueva.date()

    venta.cambiar_fecha.side_effect = _cambiar_fecha
    return venta


def _make_repos(venta: MagicMock | None = None) -> tuple[MagicMock, MagicMock]:
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta
    auditoria_repo = MagicMock()
    return ventas_repo, auditoria_repo


def _make_cmd(
    venta_id: uuid.UUID | None = None,
    motivo: str = "Cambio de itinerario",
    nueva_fecha: datetime.datetime = _NUEVA_FECHA,
) -> EditarFechaVentaComando:
    return EditarFechaVentaComando(
        venta_id=venta_id or uuid.uuid4(),
        nueva_fecha=nueva_fecha,
        motivo=motivo,
        realizada_por_telegram_id=42,
        realizada_por_nombre="Admin",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEditarFechaVentaService:
    def test_success_cambia_fecha_y_persiste(self) -> None:
        """Happy path: both cambiar_fecha and both guardar calls are made."""
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarFechaVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        cmd = _make_cmd(venta_id=venta.id)
        service.ejecutar(cmd)

        venta.cambiar_fecha.assert_called_once_with(_NUEVA_FECHA)
        auditoria_repo.guardar.assert_called_once()
        ventas_repo.guardar.assert_called_once_with(venta)

    def test_audit_guardado_antes_que_venta(self) -> None:
        """AUDIT-FIRST: auditoria.guardar must precede ventas.guardar."""
        venta = _make_venta()

        parent = MagicMock()
        parent.ventas = MagicMock()
        parent.ventas.buscar_por_id.return_value = venta
        parent.auditoria = MagicMock()

        service = EditarFechaVentaService(ventas=parent.ventas, auditoria=parent.auditoria)
        service.ejecutar(_make_cmd(venta_id=venta.id))

        guardar_calls = [c for c in parent.mock_calls if "guardar" in str(c)]
        assert len(guardar_calls) == 2
        assert "auditoria.guardar" in str(guardar_calls[0])
        assert "ventas.guardar" in str(guardar_calls[1])

    def test_auditoria_guardar_raises_venta_never_persisted(self) -> None:
        """If audit write fails, venta must NOT be persisted."""
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        auditoria_repo.guardar.side_effect = RuntimeError("DB error")
        service = EditarFechaVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(RuntimeError):
            service.ejecutar(_make_cmd(venta_id=venta.id))

        ventas_repo.guardar.assert_not_called()

    def test_datos_previos_contiene_fecha_anterior_en_iso(self) -> None:
        """datos_previos must capture the OLD fecha before mutation."""
        venta = _make_venta()
        old_fecha = venta.fecha  # datetime.date(2026, 8, 10)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarFechaVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        service.ejecutar(_make_cmd(venta_id=venta.id))

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.datos_previos == {"fecha": old_fecha.isoformat()}

    def test_audit_record_campos_correctos(self) -> None:
        """Audit record must have the right accion, motivo, actor fields."""
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarFechaVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        cmd = EditarFechaVentaComando(
            venta_id=venta.id,
            nueva_fecha=_NUEVA_FECHA,
            motivo="  motivo con espacios  ",
            realizada_por_telegram_id=99,
            realizada_por_nombre="Propietario",
        )
        service.ejecutar(cmd)

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.accion == AccionAuditoria.EDITAR_FECHA
        assert registro.motivo == "motivo con espacios"
        assert registro.realizada_por_telegram_id == 99
        assert registro.realizada_por_nombre == "Propietario"
        assert registro.venta_id == venta.id
        assert isinstance(registro.realizada_at, datetime.datetime)
        assert registro.realizada_at.tzinfo is not None

    def test_motivo_vacio_raises_motivo_requerido_nada_guardado(self) -> None:
        """Empty motivo must raise MotivoRequerido before any persistence."""
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarFechaVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta_id=venta.id, motivo="   "))

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_motivo_cadena_vacia_raises_motivo_requerido(self) -> None:
        """Triangulation: empty string also triggers MotivoRequerido."""
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarFechaVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta_id=venta.id, motivo=""))

    def test_venta_no_encontrada_raises_venta_no_encontrada(self) -> None:
        """None from repo must raise VentaNoEncontrada — nothing persisted."""
        ventas_repo, auditoria_repo = _make_repos(venta=None)
        service = EditarFechaVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(_make_cmd())

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_venta_anulada_raises_venta_ya_anulada_nada_persistido(self) -> None:
        """cambiar_fecha on anulada venta propagates VentaYaAnulada — nothing persisted."""
        venta = _make_venta(anulada=True)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarFechaVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(VentaYaAnulada):
            service.ejecutar(_make_cmd(venta_id=venta.id))

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()
