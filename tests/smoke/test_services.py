"""Post-deploy smoke tests — verify each Railway service is running correctly.

These are external black-box tests that hit live endpoints.
Run explicitly after every deploy:

    uv run pytest tests/smoke/ -v

Required env vars:
    GARAY_WEBHOOK_URL         e.g. https://ex4ctoreservas-production.up.railway.app
    GARAY_DASHBOARD_URL       e.g. https://dashboard-production-8e25.up.railway.app
    GARAY_FORWARD_EMAIL_SECRET  the webhook HMAC secret (same value as Railway var)
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.smoke

_WEBHOOK_URL = os.environ.get("GARAY_WEBHOOK_URL", "").rstrip("/")
_DASHBOARD_URL = os.environ.get("GARAY_DASHBOARD_URL", "").rstrip("/")
_WEBHOOK_SECRET = os.environ.get("GARAY_FORWARD_EMAIL_SECRET", "")

_TIMEOUT = 15


class TestWebhookService:
    """ex4ctoreservas must serve FastAPI, not Streamlit."""

    @pytest.fixture(autouse=True)
    def require_webhook_url(self) -> None:
        if not _WEBHOOK_URL:
            pytest.skip("GARAY_WEBHOOK_URL not set")

    def test_serves_fastapi_schema(self) -> None:
        """OpenAPI schema must identify this as the Garay Tours webhook, not Streamlit HTML."""
        r = httpx.get(f"{_WEBHOOK_URL}/openapi.json", timeout=_TIMEOUT)
        assert r.status_code == 200
        assert "application/json" in r.headers.get("content-type", "")
        data: object = r.json()
        assert isinstance(data, dict)
        info = data.get("info")
        assert isinstance(info, dict)
        assert "Garay Tours" in str(info.get("title", ""))

    def test_rejects_wrong_secret(self) -> None:
        """Webhook must return 403 for any invalid secret."""
        r = httpx.post(
            f"{_WEBHOOK_URL}/webhook/email?secret=invalid-smoke-secret",
            json={
                "message_id": "smoke-reject",
                "remitente_email": "x@x.com",
                "correo_destinatario": "x@x.com",
                "asunto": "",
                "cuerpo_html": "",
                "cuerpo_texto": "",
            },
            timeout=_TIMEOUT,
        )
        assert r.status_code == 403

    def test_accepts_valid_secret_unknown_bank(self) -> None:
        """Webhook must return 200 for valid secret even when the bank is not recognized.

        Uses a sender domain that will never match any bank pattern,
        so no ingreso or egreso is created in production.
        """
        if not _WEBHOOK_SECRET:
            pytest.skip("GARAY_FORWARD_EMAIL_SECRET not set")
        r = httpx.post(
            f"{_WEBHOOK_URL}/webhook/email?secret={_WEBHOOK_SECRET}",
            json={
                "message_id": "smoke-valid-unknown-bank",
                "remitente_email": "noreply@smoke-test.invalid",
                "correo_destinatario": "smoke@garay.test",
                "asunto": "smoke test — not a real email",
                "cuerpo_html": "",
                "cuerpo_texto": "smoke test body — not a real bank email",
            },
            timeout=_TIMEOUT,
        )
        assert r.status_code == 200
        result: object = r.json()
        assert isinstance(result, dict)
        assert result.get("estado") == "ok"


class TestDashboardService:
    """dashboard service must serve Streamlit, not FastAPI."""

    @pytest.fixture(autouse=True)
    def require_dashboard_url(self) -> None:
        if not _DASHBOARD_URL:
            pytest.skip("GARAY_DASHBOARD_URL not set")

    def test_streamlit_health_ok(self) -> None:
        """Streamlit health endpoint must respond with 'ok'."""
        r = httpx.get(f"{_DASHBOARD_URL}/_stcore/health", timeout=_TIMEOUT)
        assert r.status_code == 200
        assert r.text.strip() == "ok"

    def test_not_serving_fastapi(self) -> None:
        """Dashboard must NOT return a JSON OpenAPI schema (it is Streamlit, not FastAPI)."""
        r = httpx.get(f"{_DASHBOARD_URL}/openapi.json", timeout=_TIMEOUT)
        content_type = r.headers.get("content-type", "")
        assert "application/json" not in content_type, (
            f"Dashboard is serving FastAPI instead of Streamlit — content-type: {content_type}"
        )
