"""Tests for the AuditoriaVenta domain entity and AccionAuditoria enum."""

from __future__ import annotations

import datetime
import uuid

from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta


def test_auditoria_venta_holds_fields() -> None:
    venta_id = uuid.uuid4()
    audit_id = uuid.uuid4()
    at = datetime.datetime(2026, 8, 11, 10, 0, 0)
    datos = {"valor_venta": "500000", "estado": "PENDIENTE"}

    registro = AuditoriaVenta(
        id=audit_id,
        venta_id=venta_id,
        accion=AccionAuditoria.ANULAR,
        motivo="Test anulacion",
        realizada_por_telegram_id=123456789,
        realizada_por_nombre="Admin User",
        realizada_at=at,
        datos_previos=datos,
    )

    assert registro.id == audit_id
    assert registro.venta_id == venta_id
    assert registro.accion == AccionAuditoria.ANULAR
    assert registro.motivo == "Test anulacion"
    assert registro.realizada_por_telegram_id == 123456789
    assert registro.realizada_por_nombre == "Admin User"
    assert registro.realizada_at == at
    assert registro.datos_previos == datos


def test_auditoria_venta_datos_previos_defaults_to_none() -> None:
    registro = AuditoriaVenta(
        id=uuid.uuid4(),
        venta_id=uuid.uuid4(),
        accion=AccionAuditoria.EDITAR_FECHA,
        motivo="Cambio de fecha",
        realizada_por_telegram_id=987654321,
        realizada_por_nombre=None,
        realizada_at=datetime.datetime(2026, 8, 11, 12, 0, 0),
    )
    assert registro.datos_previos is None


def test_accion_auditoria_values() -> None:
    assert AccionAuditoria.ANULAR == "ANULAR"
    assert AccionAuditoria.EDITAR_FECHA == "EDITAR_FECHA"
