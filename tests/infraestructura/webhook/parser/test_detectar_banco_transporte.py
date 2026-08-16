"""Tests for Uber/DiDi bank detection and es_banco_transporte helper in base.py."""

from __future__ import annotations

from garay.infraestructura.webhook.parser.base import (
    _KEYWORDS_EGRESO,
    _SENALES_TRANSACCION,
    BANCO_DIDI,
    BANCO_UBER,
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
        # A real subdomain: notify.co.didiglobal.com ends with ".co.didiglobal.com"
        assert detectar_banco("noreply@notify.co.didiglobal.com") == "DiDi"

    def test_dominio_didi_exacto_sigue_funcionando(self) -> None:
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

    def test_none_no_es_transporte(self) -> None:
        """es_banco_transporte(None) must return False, not raise TypeError."""
        assert es_banco_transporte(None) is False


class TestSenalesNoContaminadas:
    def test_senales_transaccion_sin_uber(self) -> None:
        assert "uber" not in _SENALES_TRANSACCION

    def test_senales_transaccion_sin_didi(self) -> None:
        assert "didi" not in _SENALES_TRANSACCION

    def test_keywords_egreso_sin_uber(self) -> None:
        assert "uber" not in _KEYWORDS_EGRESO

    def test_keywords_egreso_sin_didi(self) -> None:
        assert "didi" not in _KEYWORDS_EGRESO

    # FIX 5: assert the actual title-case constants are absent, not just lowercase
    def test_senales_transaccion_sin_constante_banco_uber(self) -> None:
        assert BANCO_UBER not in _SENALES_TRANSACCION

    def test_senales_transaccion_sin_constante_banco_didi(self) -> None:
        assert BANCO_DIDI not in _SENALES_TRANSACCION

    def test_keywords_egreso_sin_constante_banco_uber(self) -> None:
        assert BANCO_UBER not in _KEYWORDS_EGRESO

    def test_keywords_egreso_sin_constante_banco_didi(self) -> None:
        assert BANCO_DIDI not in _KEYWORDS_EGRESO
