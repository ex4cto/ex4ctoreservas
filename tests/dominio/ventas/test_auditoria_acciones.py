"""Tests for new AccionAuditoria enum members — Phase 2.2 RED."""

from __future__ import annotations


class TestAccionAuditoriaExtension:
    """EDITAR_NETO and EDITAR_VALOR_VENTA must be accessible without AttributeError."""

    def test_editar_neto_accessible(self) -> None:
        from garay.dominio.ventas.auditoria import AccionAuditoria

        assert AccionAuditoria.EDITAR_NETO == "EDITAR_NETO"

    def test_editar_valor_venta_accessible(self) -> None:
        from garay.dominio.ventas.auditoria import AccionAuditoria

        assert AccionAuditoria.EDITAR_VALOR_VENTA == "EDITAR_VALOR_VENTA"

    def test_existing_members_unchanged(self) -> None:
        from garay.dominio.ventas.auditoria import AccionAuditoria

        assert AccionAuditoria.EDITAR_FECHA == "EDITAR_FECHA"
        assert AccionAuditoria.EDITAR_CLIENTE == "EDITAR_CLIENTE"
        assert AccionAuditoria.ANULAR == "ANULAR"
        assert AccionAuditoria.EDITAR_CANAL == "EDITAR_CANAL"
        assert AccionAuditoria.EDITAR_PARTICIPANTES == "EDITAR_PARTICIPANTES"
