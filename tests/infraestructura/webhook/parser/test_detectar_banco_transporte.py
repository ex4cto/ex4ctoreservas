"""Tests for Uber/DiDi bank detection and es_banco_transporte helper in base.py."""

from __future__ import annotations

from garay.infraestructura.webhook.parser.base import (
    _KEYWORDS_EGRESO,
    _SENALES_TRANSACCION,
    detectar_banco,
    es_banco_transporte,
)


class TestDetectarBancoUber:
    def test_dominio_uber_directo(self) -> None:
        assert detectar_banco("noreply@uber.com") == "Uber"

    def test_subdominio_uber(self) -> None:
        assert detectar_banco("soporte@payments.uber.com") == "Uber"


class TestDetectarBancoDiDi:
    def test_dominio_didi_directo(self) -> None:
        assert detectar_banco("didi@co.didiglobal.com") == "DiDi"

    def test_subdominio_didi(self) -> None:
        assert detectar_banco("noreply@co.didiglobal.com") == "DiDi"


class TestEsBancoTransporte:
    def test_uber_es_transporte(self) -> None:
        assert es_banco_transporte("Uber") is True

    def test_didi_es_transporte(self) -> None:
        assert es_banco_transporte("DiDi") is True

    def test_nequi_no_es_transporte(self) -> None:
        assert es_banco_transporte("Nequi") is False

    def test_bancolombia_no_es_transporte(self) -> None:
        assert es_banco_transporte("Bancolombia") is False

    def test_pse_no_es_transporte(self) -> None:
        assert es_banco_transporte("PSE") is False


class TestSenalesNoContaminadas:
    def test_senales_transaccion_sin_uber(self) -> None:
        assert "uber" not in _SENALES_TRANSACCION

    def test_senales_transaccion_sin_didi(self) -> None:
        assert "didi" not in _SENALES_TRANSACCION

    def test_keywords_egreso_sin_uber(self) -> None:
        assert "uber" not in _KEYWORDS_EGRESO

    def test_keywords_egreso_sin_didi(self) -> None:
        assert "didi" not in _KEYWORDS_EGRESO
