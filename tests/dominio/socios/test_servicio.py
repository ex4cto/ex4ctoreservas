"""Tests for calcular_split_venta pure domain function — TDD RED phase."""

from __future__ import annotations

from decimal import Decimal

from garay.dominio.comun.dinero import Dinero
from garay.dominio.socios.entidades import SocioConfig
from garay.dominio.socios.servicio import calcular_split_venta


def _config(nombre: str, porcentaje: str) -> SocioConfig:
    return SocioConfig(nombre=nombre, porcentaje=Decimal(porcentaje), telegram_id=None)


class TestCalcularSplitVenta:
    def test_split_exactamente_divisible(self) -> None:
        """50/25/25 con monto que divide exacto."""
        agencia = Dinero("1000000")
        socios = [
            _config("empresa", "50"),
            _config("garay", "25"),
            _config("ryan", "25"),
        ]
        resultado = calcular_split_venta(agencia, socios)

        assert resultado["empresa"] == Dinero("500000")
        assert resultado["garay"] == Dinero("250000")
        assert resultado["ryan"] == Dinero("250000")

    def test_split_con_residuo_va_al_ultimo(self) -> None:
        """Centavos residuales van al último socio de la lista."""
        # 100 / 3 = 33.33... cada uno → residuo de 0.01
        agencia = Dinero("100")
        socios = [
            _config("empresa", "33"),
            _config("garay", "33"),
            _config("ryan", "34"),
        ]
        resultado = calcular_split_venta(agencia, socios)

        # empresa: 100 * 33 / 100 = 33.00
        # garay:   100 * 33 / 100 = 33.00
        # ryan: residuo = 100 - 33 - 33 = 34.00
        assert resultado["empresa"] == Dinero("33")
        assert resultado["garay"] == Dinero("33")
        assert resultado["ryan"] == Dinero("34")

    def test_suma_siempre_igual_a_agencia(self) -> None:
        """Invariante: sum(splits) == agencia, sin importar el redondeo."""
        agencia = Dinero("999999")
        socios = [
            _config("empresa", "50"),
            _config("garay", "25"),
            _config("ryan", "25"),
        ]
        resultado = calcular_split_venta(agencia, socios)
        suma = sum(resultado.values(), start=Dinero(0))
        assert suma == agencia

    def test_invariante_con_residuo_centimos(self) -> None:
        """Invariante se mantiene cuando hay residuo de centavos."""
        agencia = Dinero("100.01")
        socios = [
            _config("empresa", "50"),
            _config("garay", "25"),
            _config("ryan", "25"),
        ]
        resultado = calcular_split_venta(agencia, socios)
        suma = sum(resultado.values(), start=Dinero(0))
        assert suma == agencia

    def test_lista_vacia_de_socios_retorna_dict_vacio(self) -> None:
        agencia = Dinero("500000")
        resultado = calcular_split_venta(agencia, [])
        assert resultado == {}

    def test_un_solo_socio_recibe_todo(self) -> None:
        agencia = Dinero("750000")
        socios = [_config("empresa", "100")]
        resultado = calcular_split_venta(agencia, socios)
        assert resultado["empresa"] == agencia

    def test_retorna_dict_con_nombres_como_claves(self) -> None:
        agencia = Dinero("300000")
        socios = [
            _config("empresa", "50"),
            _config("garay", "25"),
            _config("ryan", "25"),
        ]
        resultado = calcular_split_venta(agencia, socios)
        assert set(resultado.keys()) == {"empresa", "garay", "ryan"}
