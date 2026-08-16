"""Smoke tests for the ContadorFacturasEnviadas port interface.

Verifies that:
- The ABC exists and is importable.
- Concrete subclasses MUST implement both abstract methods.
- The interface signature matches the contract (contar_mes_a_la_fecha + contar_dia).
"""

from __future__ import annotations

import datetime
import inspect

import pytest

from garay.dominio.puertos.contador_facturas import ContadorFacturasEnviadas


class TestContadorFacturasEnviadasInterface:
    def test_es_abstracta_no_instanciable_directamente(self) -> None:
        """ABC cannot be instantiated without implementing abstract methods."""
        with pytest.raises(TypeError):
            ContadorFacturasEnviadas()  # type: ignore[abstract]

    def test_tiene_metodo_contar_mes_a_la_fecha(self) -> None:
        assert hasattr(ContadorFacturasEnviadas, "contar_mes_a_la_fecha")

    def test_tiene_metodo_contar_dia(self) -> None:
        assert hasattr(ContadorFacturasEnviadas, "contar_dia")

    def test_contar_mes_a_la_fecha_es_abstracto(self) -> None:
        assert getattr(
            ContadorFacturasEnviadas.contar_mes_a_la_fecha, "__isabstractmethod__", False
        )

    def test_contar_dia_es_abstracto(self) -> None:
        assert getattr(
            ContadorFacturasEnviadas.contar_dia, "__isabstractmethod__", False
        )

    def test_concrete_subclass_sin_implementar_falla(self) -> None:
        """A partial subclass (missing one method) cannot be instantiated."""

        class Incompleto(ContadorFacturasEnviadas):
            def contar_mes_a_la_fecha(self, hasta: datetime.date) -> int:
                return 0

            # contar_dia intentionally NOT implemented

        with pytest.raises(TypeError):
            Incompleto()  # type: ignore[abstract]

    def test_concrete_subclass_completa_instancia_correctamente(self) -> None:
        """A fully implemented subclass can be instantiated."""

        class FakeContador(ContadorFacturasEnviadas):
            def contar_mes_a_la_fecha(self, hasta: datetime.date) -> int:
                return 42

            def contar_dia(self, dia: datetime.date) -> int:
                return 7

        contador = FakeContador()
        assert contador.contar_mes_a_la_fecha(datetime.date(2026, 8, 15)) == 42
        assert contador.contar_dia(datetime.date(2026, 8, 15)) == 7
