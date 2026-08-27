"""Tests for the public /logo.png route.

Emailed invoices reference the logo by public URL because email clients block
`data:` URI images. This route serves the logo from the web service.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class TestLogoRoute:
    def test_logo_devuelve_png(self, client: TestClient) -> None:
        resp = client.get("/logo.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == _PNG_MAGIC

    def test_logo_tiene_cache_header(self, client: TestClient) -> None:
        resp = client.get("/logo.png")
        assert "max-age" in resp.headers.get("cache-control", "")
