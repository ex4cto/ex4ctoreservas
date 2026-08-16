"""Tests for ProveedorUsoRailway port interface.

Verifies that:
- The ABC exists and is importable.
- It cannot be instantiated without implementing abstract methods.
- A complete concrete subclass can be instantiated and its methods called.
- Method signatures match the contract.
"""

from __future__ import annotations

import datetime

import pytest

from garay.dominio.puertos.proveedor_uso_railway import ProveedorUsoRailway


class TestProveedorUsoRailwayInterface:
    def test_es_abstracta_no_instanciable_directamente(self) -> None:
        """ABC cannot be instantiated without implementing abstract methods."""
        with pytest.raises(TypeError):
            ProveedorUsoRailway()  # type: ignore[abstract]

    def test_tiene_metodo_uso_mes_a_la_fecha(self) -> None:
        assert hasattr(ProveedorUsoRailway, "uso_mes_a_la_fecha")

    def test_tiene_metodo_estimado_mes(self) -> None:
        assert hasattr(ProveedorUsoRailway, "estimado_mes")

    def test_uso_mes_a_la_fecha_es_abstracto(self) -> None:
        assert getattr(
            ProveedorUsoRailway.uso_mes_a_la_fecha, "__isabstractmethod__", False
        )

    def test_estimado_mes_es_abstracto(self) -> None:
        assert getattr(
            ProveedorUsoRailway.estimado_mes, "__isabstractmethod__", False
        )

    def test_subclase_incompleta_no_instanciable(self) -> None:
        """A subclass missing one abstract method cannot be instantiated."""

        class Incompleto(ProveedorUsoRailway):
            def uso_mes_a_la_fecha(self, hasta: datetime.date) -> dict[str, float]:
                return {}

            # estimado_mes intentionally NOT implemented

        with pytest.raises(TypeError):
            Incompleto()  # type: ignore[abstract]

    def test_subclase_completa_instanciable_y_funcional(self) -> None:
        """A fully implemented subclass can be instantiated and called."""

        class FakeProveedor(ProveedorUsoRailway):
            def uso_mes_a_la_fecha(self, hasta: datetime.date) -> dict[str, float]:
                return {"MEMORY_USAGE_GB": 500.0, "CPU_USAGE": 200.0}

            def estimado_mes(self, hoy: datetime.date) -> dict[str, float]:
                return {"MEMORY_USAGE_GB": 1000.0, "CPU_USAGE": 400.0}

        proveedor = FakeProveedor()
        fecha = datetime.date(2026, 8, 15)
        resultado_uso = proveedor.uso_mes_a_la_fecha(fecha)
        assert resultado_uso["MEMORY_USAGE_GB"] == 500.0
        assert resultado_uso["CPU_USAGE"] == 200.0

        resultado_estimado = proveedor.estimado_mes(fecha)
        assert resultado_estimado["MEMORY_USAGE_GB"] == 1000.0
