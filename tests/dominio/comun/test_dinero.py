"""Tests del value object Dinero. Base de toda la logica monetaria."""

from __future__ import annotations

from decimal import Decimal

import pytest

from garay.dominio.comun.dinero import Dinero, MonedaIncompatible, MontoInvalido


class TestCreacion:
    def test_crea_desde_entero(self) -> None:
        assert Dinero(1000).monto == Decimal("1000.00")

    def test_crea_desde_string(self) -> None:
        assert Dinero("1000.50").monto == Decimal("1000.50")

    def test_crea_desde_decimal(self) -> None:
        assert Dinero(Decimal("999.99")).monto == Decimal("999.99")

    def test_moneda_predeterminada_es_cop(self) -> None:
        assert Dinero(1000).moneda == "COP"

    def test_rechaza_float_para_evitar_imprecision(self) -> None:
        with pytest.raises(MontoInvalido):
            Dinero(1000.5)  # type: ignore[arg-type]

    def test_rechaza_valor_no_numerico(self) -> None:
        with pytest.raises(MontoInvalido):
            Dinero("no-es-un-numero")

    def test_es_inmutable(self) -> None:
        dinero = Dinero(1000)
        with pytest.raises(AttributeError):
            dinero.monto = Decimal("2000")  # type: ignore[misc]


class TestIgualdad:
    def test_igual_mismo_monto_y_moneda(self) -> None:
        assert Dinero(1000) == Dinero("1000")

    def test_distinto_monto(self) -> None:
        assert Dinero(1000) != Dinero(999)

    def test_distinta_moneda_no_es_igual(self) -> None:
        assert Dinero(1000, "COP") != Dinero(1000, "USD")

    def test_hasheable(self) -> None:
        assert len({Dinero(1000), Dinero("1000"), Dinero(500)}) == 2


class TestAritmetica:
    def test_suma(self) -> None:
        assert Dinero(1000) + Dinero(500) == Dinero(1500)

    def test_resta(self) -> None:
        assert Dinero(1000) - Dinero(500) == Dinero(500)

    def test_resta_puede_ser_negativa(self) -> None:
        assert Dinero(500) - Dinero(1000) == Dinero(-500)

    def test_suma_distinta_moneda_falla(self) -> None:
        with pytest.raises(MonedaIncompatible):
            Dinero(1000, "COP") + Dinero(1000, "USD")

    def test_multiplica_por_decimal(self) -> None:
        assert Dinero(1000) * Decimal("0.2") == Dinero(200)

    def test_multiplica_rechaza_float(self) -> None:
        with pytest.raises(MontoInvalido):
            Dinero(1000) * 0.2  # type: ignore[operator]


class TestPorcentaje:
    def test_aplica_porcentaje_entero(self) -> None:
        assert Dinero(1000).aplicar_porcentaje(Decimal("20")) == Dinero(200)

    def test_aplica_porcentaje_redondea_half_up(self) -> None:
        # 33.333% de 100 = 33.333 -> 33.33
        assert Dinero("100").aplicar_porcentaje(Decimal("33.333")) == Dinero("33.33")


class TestComparacion:
    def test_orden(self) -> None:
        assert Dinero(500) < Dinero(1000)
        assert Dinero(1000) > Dinero(500)

    def test_comparar_distinta_moneda_falla(self) -> None:
        with pytest.raises(MonedaIncompatible):
            _ = Dinero(1000, "COP") < Dinero(1000, "USD")
