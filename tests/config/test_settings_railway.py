"""Tests for Settings fields added by monitor-costo-railway (Batch 1).

Covers:
- railway_api_token: str (default "", GARAY_RAILWAY_API_TOKEN)
- railway_project_id: str (default "", reads RAILWAY_PROJECT_ID — no GARAY_ prefix)
- railway_umbral_costo: float (default 20.0, GARAY_RAILWAY_UMBRAL_COSTO)
- railway_precio_memoria_gb_min: float (default 0.000231)
- railway_precio_cpu_vcpu_min: float (default 0.000463)
- railway_precio_egress_gb: float (default 0.05)
- railway_precio_volumen_gb_min: float (default 0.000003)
- railway_plan_fee: float (default 5.0)
"""

from __future__ import annotations

import pytest

from garay.config.settings import Settings


class TestRailwayApiToken:
    def test_default_es_string_vacio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_RAILWAY_API_TOKEN", raising=False)
        settings = Settings()
        assert settings.railway_api_token == ""

    def test_parsea_desde_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GARAY_RAILWAY_API_TOKEN", "tok_abc123")
        settings = Settings()
        assert settings.railway_api_token == "tok_abc123"


class TestRailwayProjectId:
    def test_default_es_string_vacio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)
        monkeypatch.delenv("GARAY_RAILWAY_PROJECT_ID", raising=False)
        settings = Settings()
        assert settings.railway_project_id == ""

    def test_lee_desde_railway_project_id_sin_prefijo_garay(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The field must read RAILWAY_PROJECT_ID (no GARAY_ prefix) — this
        is the env var Railway injects automatically into deployments."""
        monkeypatch.delenv("GARAY_RAILWAY_PROJECT_ID", raising=False)
        monkeypatch.setenv("RAILWAY_PROJECT_ID", "proj-xyz-789")
        settings = Settings()
        assert settings.railway_project_id == "proj-xyz-789"

    def test_no_lee_garay_railway_project_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GARAY_RAILWAY_PROJECT_ID (with prefix) must NOT satisfy this field.
        The field is deliberately un-prefixed — it relies on RAILWAY_PROJECT_ID only."""
        monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)
        monkeypatch.delenv("GARAY_RAILWAY_PROJECT_ID", raising=False)
        # Setting only the GARAY_ variant should leave the field empty
        monkeypatch.setenv("GARAY_RAILWAY_PROJECT_ID", "should-be-ignored")
        settings = Settings()
        assert settings.railway_project_id == ""


class TestRailwayUmbralCosto:
    def test_default_es_20(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_RAILWAY_UMBRAL_COSTO", raising=False)
        settings = Settings()
        assert settings.railway_umbral_costo == 20.0

    def test_parsea_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GARAY_RAILWAY_UMBRAL_COSTO", "35.0")
        settings = Settings()
        assert settings.railway_umbral_costo == 35.0


class TestRailwayPrecios:
    def test_precio_memoria_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_RAILWAY_PRECIO_MEMORIA_GB_MIN", raising=False)
        settings = Settings()
        assert settings.railway_precio_memoria_gb_min == pytest.approx(0.000231)

    def test_precio_cpu_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_RAILWAY_PRECIO_CPU_VCPU_MIN", raising=False)
        settings = Settings()
        assert settings.railway_precio_cpu_vcpu_min == pytest.approx(0.000463)

    def test_precio_egress_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_RAILWAY_PRECIO_EGRESS_GB", raising=False)
        settings = Settings()
        assert settings.railway_precio_egress_gb == pytest.approx(0.05)

    def test_precio_volumen_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_RAILWAY_PRECIO_VOLUMEN_GB_MIN", raising=False)
        settings = Settings()
        assert settings.railway_precio_volumen_gb_min == pytest.approx(0.000003)


class TestRailwayPlanFee:
    def test_default_es_5(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GARAY_RAILWAY_PLAN_FEE", raising=False)
        settings = Settings()
        assert settings.railway_plan_fee == pytest.approx(5.0)

    def test_parsea_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GARAY_RAILWAY_PLAN_FEE", "10.0")
        settings = Settings()
        assert settings.railway_plan_fee == pytest.approx(10.0)
