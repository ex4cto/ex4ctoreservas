"""Tests for task 1.10: PagoReferidoRepository ABC."""

from __future__ import annotations

from abc import ABC


class TestPagoReferidoRepository:
    def test_pago_referido_repository_is_importable(self) -> None:
        """Task 1.10: PagoReferidoRepository must exist in puertos.repositorios."""
        from garay.dominio.puertos.repositorios import PagoReferidoRepository

        assert PagoReferidoRepository is not None

    def test_pago_referido_repository_is_abstract(self) -> None:
        from garay.dominio.puertos.repositorios import PagoReferidoRepository

        assert issubclass(PagoReferidoRepository, ABC)

    def test_pago_referido_repository_has_guardar(self) -> None:
        from garay.dominio.puertos.repositorios import PagoReferidoRepository

        assert hasattr(PagoReferidoRepository, "guardar")

    def test_pago_referido_repository_has_listar_por_venta(self) -> None:
        from garay.dominio.puertos.repositorios import PagoReferidoRepository

        assert hasattr(PagoReferidoRepository, "listar_por_venta")

    def test_pago_referido_repository_has_listar_por_referido(self) -> None:
        from garay.dominio.puertos.repositorios import PagoReferidoRepository

        assert hasattr(PagoReferidoRepository, "listar_por_referido")

    def test_pago_referido_repository_has_buscar_solapados(self) -> None:
        """Task 1.10: buscar_solapados(alias, desde, hasta) must be declared."""
        from garay.dominio.puertos.repositorios import PagoReferidoRepository

        assert hasattr(PagoReferidoRepository, "buscar_solapados")

    def test_pago_referido_repository_has_eliminar(self) -> None:
        """Task 1.10: eliminar must be declared."""
        from garay.dominio.puertos.repositorios import PagoReferidoRepository

        assert hasattr(PagoReferidoRepository, "eliminar")
