"""Tests for new edit-time domain error classes — Phase 2.1 RED."""

from __future__ import annotations

import pytest

from garay.dominio.comun.errores import ErrorDeDominio


class TestNuevosErroresEdicion:
    """The four new error classes must exist and be subtypes of ErrorDeDominio."""

    def test_neto_igual_o_supera_valor_venta_es_error_de_dominio(self) -> None:
        from garay.dominio.ventas.errores import NetoIgualOSuperaValorVenta

        err = NetoIgualOSuperaValorVenta("neto >= valor_venta")
        assert isinstance(err, ErrorDeDominio)

    def test_valor_venta_menor_que_abono_es_error_de_dominio(self) -> None:
        from garay.dominio.ventas.errores import ValorVentaMenorQueAbono

        err = ValorVentaMenorQueAbono("valor_venta < abono")
        assert isinstance(err, ErrorDeDominio)

    def test_mismo_neto_es_error_de_dominio(self) -> None:
        from garay.dominio.ventas.errores import MismoNeto

        err = MismoNeto("neto ya es ese valor")
        assert isinstance(err, ErrorDeDominio)

    def test_mismo_valor_venta_es_error_de_dominio(self) -> None:
        from garay.dominio.ventas.errores import MismoValorVenta

        err = MismoValorVenta("valor_venta ya es ese valor")
        assert isinstance(err, ErrorDeDominio)

    def test_todos_los_errores_son_instancias_de_exception(self) -> None:
        from garay.dominio.ventas.errores import (
            MismoNeto,
            MismoValorVenta,
            NetoIgualOSuperaValorVenta,
            ValorVentaMenorQueAbono,
        )

        for cls in (
            NetoIgualOSuperaValorVenta,
            ValorVentaMenorQueAbono,
            MismoNeto,
            MismoValorVenta,
        ):
            with pytest.raises(cls):
                raise cls("test")
