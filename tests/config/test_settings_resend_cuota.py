"""Tests for Settings fields added by monitor-resend-cuota (Batch 1).

Covers:
- resend_cap_mensual: int (default 3000, GARAY_RESEND_CAP_MENSUAL env)
- resend_cap_diario: int (default 100, GARAY_RESEND_CAP_DIARIO env)
- resend_bandas_mensual: tuple[float, ...] (default (0.80, 0.95, 1.0))
- resend_umbral_diario: int (default 80, GARAY_RESEND_UMBRAL_DIARIO env)
"""

from __future__ import annotations

import pytest

from garay.config.settings import Settings


class TestResendCapMensual:
    def test_default_es_3000(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_RESEND_CAP_MENSUAL", raising=False)
        settings = Settings()
        assert settings.resend_cap_mensual == 3000

    def test_parsea_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GARAY_RESEND_CAP_MENSUAL", "5000")
        settings = Settings()
        assert settings.resend_cap_mensual == 5000


class TestResendCapDiario:
    def test_default_es_100(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_RESEND_CAP_DIARIO", raising=False)
        settings = Settings()
        assert settings.resend_cap_diario == 100

    def test_parsea_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GARAY_RESEND_CAP_DIARIO", "200")
        settings = Settings()
        assert settings.resend_cap_diario == 200


class TestResendBandasMensual:
    def test_default_es_fracciones_estandar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GARAY_RESEND_BANDAS_MENSUAL", raising=False)
        settings = Settings()
        assert settings.resend_bandas_mensual == (0.80, 0.95, 1.0)

    def test_parsea_bandas_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GARAY_RESEND_BANDAS_MENSUAL", "[0.5,0.75,1.0]")
        settings = Settings()
        assert settings.resend_bandas_mensual == (0.5, 0.75, 1.0)


class TestResendUmbralDiario:
    def test_default_es_80(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_RESEND_UMBRAL_DIARIO", raising=False)
        settings = Settings()
        assert settings.resend_umbral_diario == 80

    def test_parsea_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GARAY_RESEND_UMBRAL_DIARIO", "90")
        settings = Settings()
        assert settings.resend_umbral_diario == 90
