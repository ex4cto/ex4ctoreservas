"""Tests that main.py wires LiquidarReferidoService and SQLAPagoReferidoRepository.

Task 5.4: assert the referido services are importable from main.py and
that LiquidarReferidoService accepts a pago_referido_repo argument.
"""

from __future__ import annotations

import inspect


class TestMainModuleImports:
    """main.py must import the referido services so they are available at wire time."""

    def test_sqla_pago_referido_repository_importable(self) -> None:
        """SQLAPagoReferidoRepository must be importable from its infra module."""
        from garay.infraestructura.persistencia.repositorios.pago_referido import (
            SQLAPagoReferidoRepository,
        )
        assert SQLAPagoReferidoRepository is not None

    def test_liquidar_referido_service_importable(self) -> None:
        """LiquidarReferidoService must be importable from aplicacion.liquidaciones."""
        from garay.aplicacion.liquidaciones.servicio import LiquidarReferidoService
        assert LiquidarReferidoService is not None

    def test_main_py_imports_liquidar_referido_service(self) -> None:
        """main.py source must reference LiquidarReferidoService."""
        import garay.infraestructura.telegram.main as main_module
        src = inspect.getsource(main_module)
        assert "LiquidarReferidoService" in src, (
            "LiquidarReferidoService not found in main.py source"
        )

    def test_main_py_imports_sqla_pago_referido_repository(self) -> None:
        """main.py source must reference SQLAPagoReferidoRepository."""
        import garay.infraestructura.telegram.main as main_module
        src = inspect.getsource(main_module)
        assert "SQLAPagoReferidoRepository" in src, (
            "SQLAPagoReferidoRepository not found in main.py source"
        )

    def test_main_py_wires_liquidar_referido_service_in_bot_data(self) -> None:
        """main.py source must store liquidar_referido_service in bot_data."""
        import garay.infraestructura.telegram.main as main_module
        src = inspect.getsource(main_module)
        assert "liquidar_referido_service" in src, (
            "'liquidar_referido_service' key not found in main.py source"
        )


class TestLiquidarReferidoServiceInterface:
    """LiquidarReferidoService must accept pago_referido_repo as constructor arg."""

    def test_liquidar_referido_service_accepts_pago_referido_repo(self) -> None:
        """LiquidarReferidoService.__init__ must have pago_referido_repo param."""
        from garay.aplicacion.liquidaciones.servicio import LiquidarReferidoService
        sig = inspect.signature(LiquidarReferidoService.__init__)
        assert "pago_referido_repo" in sig.parameters, (
            f"pago_referido_repo not in LiquidarReferidoService.__init__ params: "
            f"{list(sig.parameters.keys())}"
        )
