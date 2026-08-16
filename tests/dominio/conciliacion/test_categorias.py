"""Tests for dominio/conciliacion/categorias.py — category constants and banco_a_categoria."""

from __future__ import annotations

from garay.dominio.conciliacion.categorias import (
    CATEGORIA_OTRO,
    CATEGORIA_TRANSPORTE,
    banco_a_categoria,
)


class TestConstantes:
    def test_categoria_transporte_valor(self) -> None:
        assert CATEGORIA_TRANSPORTE == "transporte"

    def test_categoria_otro_valor(self) -> None:
        assert CATEGORIA_OTRO == "otro"


class TestBancoACategoria:
    def test_uber_retorna_transporte(self) -> None:
        assert banco_a_categoria("Uber") == "transporte"

    def test_didi_retorna_transporte(self) -> None:
        assert banco_a_categoria("DiDi") == "transporte"

    def test_nequi_retorna_otro(self) -> None:
        assert banco_a_categoria("Nequi") == "otro"

    def test_bancolombia_retorna_otro(self) -> None:
        assert banco_a_categoria("Bancolombia") == "otro"

    def test_pse_retorna_otro(self) -> None:
        assert banco_a_categoria("PSE") == "otro"

    def test_banco_desconocido_retorna_otro(self) -> None:
        assert banco_a_categoria("unknown_bank") == "otro"
