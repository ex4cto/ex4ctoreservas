"""Tests for limite_ediciones financial/informational split — Phase 2.5 RED."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

import pytest

from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.errores import LimiteEdicionesAlcanzado


def _audit_record(accion: AccionAuditoria) -> AuditoriaVenta:
    return AuditoriaVenta(
        id=uuid.uuid4(),
        venta_id=uuid.uuid4(),
        accion=accion,
        motivo="test",
        realizada_por_telegram_id=1,
        realizada_por_nombre=None,
        realizada_at=datetime.datetime.now(datetime.UTC),
    )


def _mock_auditoria(acciones: list[AccionAuditoria]) -> MagicMock:
    mock = MagicMock()
    mock.listar_por_venta_id.return_value = [_audit_record(a) for a in acciones]
    return mock


class TestVerificarLimiteEdicionesFinanciero:
    """Financial verifier enforces MAX=3 counting EDITAR_CANAL + EDITAR_NETO + EDITAR_VALOR_VENTA."""

    def test_importable(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import (
            verificar_limite_ediciones_financiero,
        )

        assert verificar_limite_ediciones_financiero is not None

    def test_no_error_when_below_limit(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import (
            verificar_limite_ediciones_financiero,
        )

        mock_auditoria = _mock_auditoria([AccionAuditoria.EDITAR_CANAL])
        # Should not raise
        verificar_limite_ediciones_financiero(mock_auditoria, uuid.uuid4())

    def test_no_error_at_exactly_two(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import (
            verificar_limite_ediciones_financiero,
        )

        mock_auditoria = _mock_auditoria(
            [AccionAuditoria.EDITAR_CANAL, AccionAuditoria.EDITAR_NETO]
        )
        verificar_limite_ediciones_financiero(mock_auditoria, uuid.uuid4())

    def test_raises_when_at_three(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import (
            verificar_limite_ediciones_financiero,
        )

        mock_auditoria = _mock_auditoria(
            [
                AccionAuditoria.EDITAR_CANAL,
                AccionAuditoria.EDITAR_NETO,
                AccionAuditoria.EDITAR_VALOR_VENTA,
            ]
        )
        with pytest.raises(LimiteEdicionesAlcanzado):
            verificar_limite_ediciones_financiero(mock_auditoria, uuid.uuid4())

    def test_historical_editar_canal_counts(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import (
            verificar_limite_ediciones_financiero,
        )

        mock_auditoria = _mock_auditoria(
            [
                AccionAuditoria.EDITAR_CANAL,
                AccionAuditoria.EDITAR_CANAL,
                AccionAuditoria.EDITAR_CANAL,
            ]
        )
        with pytest.raises(LimiteEdicionesAlcanzado):
            verificar_limite_ediciones_financiero(mock_auditoria, uuid.uuid4())

    def test_informational_edits_not_counted(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import (
            verificar_limite_ediciones_financiero,
        )

        mock_auditoria = _mock_auditoria(
            [
                AccionAuditoria.EDITAR_FECHA,
                AccionAuditoria.EDITAR_CLIENTE,
                AccionAuditoria.EDITAR_PARTICIPANTES,
                AccionAuditoria.EDITAR_FECHA,
            ]
        )
        # 4 informational edits — should NOT trigger financial limit
        verificar_limite_ediciones_financiero(mock_auditoria, uuid.uuid4())


class TestVerificarLimiteEdicionesInformativo:
    """Informational verifier is a no-op; no limit applies."""

    def test_importable(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import (
            verificar_limite_ediciones_informativo,
        )

        assert verificar_limite_ediciones_informativo is not None

    def test_never_raises(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import (
            verificar_limite_ediciones_informativo,
        )

        # Even with 100 financial edits, informational verifier never raises
        mock_auditoria = _mock_auditoria(
            [AccionAuditoria.EDITAR_CANAL] * 100
        )
        verificar_limite_ediciones_informativo(mock_auditoria, uuid.uuid4())


class TestBackwardCompatAlias:
    """verificar_limite_ediciones must still exist and delegate to financial verifier."""

    def test_alias_importable(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import verificar_limite_ediciones

        assert verificar_limite_ediciones is not None

    def test_alias_raises_when_financial_limit_hit(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import verificar_limite_ediciones

        mock_auditoria = _mock_auditoria(
            [
                AccionAuditoria.EDITAR_CANAL,
                AccionAuditoria.EDITAR_NETO,
                AccionAuditoria.EDITAR_VALOR_VENTA,
            ]
        )
        with pytest.raises(LimiteEdicionesAlcanzado):
            verificar_limite_ediciones(mock_auditoria, uuid.uuid4())
