"""Tests for EditarMetodoPagoVentaService — Strict TDD."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.ventas.comandos import EditarMetodoPagoVentaComando
from garay.aplicacion.ventas.editar_metodo_pago import EditarMetodoPagoVentaService
from garay.dominio.comun.tipos import MetodoPago
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import (
    MismoMetodoPago,
    MotivoRequerido,
    VentaNoEncontrada,
    VentaYaAnulada,
)
from garay.aplicacion.ventas.limite_ediciones import ACCIONES_FINANCIERAS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_venta(
    metodo_pago: MetodoPago = MetodoPago.TRANSFERENCIA,
    anulada: bool = False,
) -> MagicMock:
    venta = MagicMock()
    venta.id = uuid.uuid4()
    venta.metodo_pago = metodo_pago
    venta.anulada = anulada

    def _cambiar_metodo_pago(nuevo: MetodoPago) -> None:
        if venta.anulada:
            raise VentaYaAnulada("Ya anulada.")
        if nuevo == venta.metodo_pago:
            raise MismoMetodoPago("Ya es ese método.")
        venta.metodo_pago = nuevo

    venta.cambiar_metodo_pago.side_effect = _cambiar_metodo_pago
    return venta


def _make_repos(venta: MagicMock | None = None) -> tuple[MagicMock, MagicMock]:
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta
    auditoria_repo = MagicMock()
    auditoria_repo.listar_por_venta_id.return_value = []
    return ventas_repo, auditoria_repo


def _make_cmd(
    venta_id: uuid.UUID | None = None,
    nuevo_metodo_pago: MetodoPago = MetodoPago.EFECTIVO,
    motivo: str = "Corrección de método",
) -> EditarMetodoPagoVentaComando:
    return EditarMetodoPagoVentaComando(
        venta_id=venta_id or uuid.uuid4(),
        nuevo_metodo_pago=nuevo_metodo_pago,
        motivo=motivo,
        realizada_por_telegram_id=42,
        realizada_por_nombre="Admin",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEditarMetodoPagoVentaService:
    def test_motivo_vacio_raises_motivo_requerido(self) -> None:
        """Empty motivo must raise MotivoRequerido before any persistence."""
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarMetodoPagoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta_id=venta.id, motivo="  "))

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_motivo_cadena_vacia_raises_motivo_requerido(self) -> None:
        """Empty string motivo also raises MotivoRequerido."""
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarMetodoPagoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta_id=venta.id, motivo=""))

    def test_venta_no_encontrada_raises_venta_no_encontrada(self) -> None:
        """None from repo must raise VentaNoEncontrada — nothing persisted."""
        ventas_repo, auditoria_repo = _make_repos(venta=None)
        service = EditarMetodoPagoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(_make_cmd())

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_mismo_metodo_pago_raises_mismo_metodo_pago(self) -> None:
        """MismoMetodoPago raised when nuevo equals current metodo_pago."""
        venta = _make_venta(metodo_pago=MetodoPago.TRANSFERENCIA)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarMetodoPagoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(MismoMetodoPago):
            service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_metodo_pago=MetodoPago.TRANSFERENCIA))

    def test_venta_anulada_raises_venta_ya_anulada(self) -> None:
        """VentaYaAnulada raised when venta is anulada — nothing persisted."""
        venta = _make_venta(anulada=True)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarMetodoPagoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(VentaYaAnulada):
            service.ejecutar(_make_cmd(venta_id=venta.id))

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_success_cambia_metodo_pago_y_persiste(self) -> None:
        """Happy path: both guardar calls are made and metodo_pago changes."""
        venta = _make_venta(metodo_pago=MetodoPago.TRANSFERENCIA)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarMetodoPagoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        cmd = _make_cmd(venta_id=venta.id, nuevo_metodo_pago=MetodoPago.EFECTIVO)
        service.ejecutar(cmd)

        venta.cambiar_metodo_pago.assert_called_once_with(MetodoPago.EFECTIVO)
        auditoria_repo.guardar.assert_called_once()
        ventas_repo.guardar.assert_called_once_with(venta)

    def test_audit_guardado_antes_que_venta(self) -> None:
        """AUDIT-FIRST: auditoria.guardar must precede ventas.guardar."""
        venta = _make_venta(metodo_pago=MetodoPago.TRANSFERENCIA)

        parent = MagicMock()
        parent.ventas = MagicMock()
        parent.ventas.buscar_por_id.return_value = venta
        parent.auditoria = MagicMock()
        parent.auditoria.listar_por_venta_id.return_value = []

        service = EditarMetodoPagoVentaService(ventas=parent.ventas, auditoria=parent.auditoria)
        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_metodo_pago=MetodoPago.EFECTIVO))

        guardar_calls = [c for c in parent.mock_calls if "guardar" in str(c)]
        assert len(guardar_calls) == 2
        assert "auditoria.guardar" in str(guardar_calls[0])
        assert "ventas.guardar" in str(guardar_calls[1])

    def test_datos_previos_contiene_metodo_pago_anterior(self) -> None:
        """datos_previos must capture the OLD metodo_pago before mutation."""
        venta = _make_venta(metodo_pago=MetodoPago.TRANSFERENCIA)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarMetodoPagoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_metodo_pago=MetodoPago.EFECTIVO))

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.datos_previos == {"metodo_pago": "TRANSFERENCIA"}

    def test_audit_record_accion_editar_metodo_pago(self) -> None:
        """Audit record must have accion=EDITAR_METODO_PAGO."""
        venta = _make_venta(metodo_pago=MetodoPago.TRANSFERENCIA)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarMetodoPagoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_metodo_pago=MetodoPago.EFECTIVO))

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.accion == AccionAuditoria.EDITAR_METODO_PAGO

    def test_editar_metodo_pago_no_esta_en_acciones_financieras(self) -> None:
        """EDITAR_METODO_PAGO must NOT be in ACCIONES_FINANCIERAS — it is informational."""
        assert AccionAuditoria.EDITAR_METODO_PAGO not in ACCIONES_FINANCIERAS
