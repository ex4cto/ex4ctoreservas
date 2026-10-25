"""Tests for task 1.8: AccionAuditoria.EDITAR_REFERIDO."""

from __future__ import annotations


class TestAccionAuditoriaEditarReferido:
    def test_editar_referido_accessible(self) -> None:
        """Task 1.8: EDITAR_REFERIDO must exist in AccionAuditoria."""
        from garay.dominio.ventas.auditoria import AccionAuditoria

        assert AccionAuditoria.EDITAR_REFERIDO == "EDITAR_REFERIDO"

    def test_editar_referido_is_str(self) -> None:
        from garay.dominio.ventas.auditoria import AccionAuditoria

        assert isinstance(AccionAuditoria.EDITAR_REFERIDO, str)
