"""Tests for Settings fields added by monitor-servicios-infra Slice 1.

Covers AC-14 / Seam 14:
- dominio_renovacion parses ISO date from env; absent → None
- dominio_bandas_aviso parses tuple from env; absent → default (60, 30, 7, 1)
"""

from __future__ import annotations

import datetime

import pytest

from garay.config.settings import Settings


class TestDominioRenovacion:
    def test_parsea_fecha_iso(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GARAY_DOMINIO_RENOVACION", "2027-03-15")
        settings = Settings()
        assert settings.dominio_renovacion == datetime.date(2027, 3, 15)

    def test_ausente_devuelve_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_DOMINIO_RENOVACION", raising=False)
        settings = Settings()
        assert settings.dominio_renovacion is None


class TestDominioBandasAviso:
    def test_parsea_bandas_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GARAY_DOMINIO_BANDAS_AVISO", "[90,45,14,3]")
        settings = Settings()
        assert settings.dominio_bandas_aviso == (90, 45, 14, 3)

    def test_default_cuando_ausente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_DOMINIO_BANDAS_AVISO", raising=False)
        settings = Settings()
        assert settings.dominio_bandas_aviso == (60, 30, 7, 1)
