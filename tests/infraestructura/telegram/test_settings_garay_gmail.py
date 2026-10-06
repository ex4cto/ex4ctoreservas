"""Tests for gmail_sharimel settings field.

Spec: verificar-pago-email-config.
The env var GARAY_GMAIL_SHARIMEL maps to settings.gmail_sharimel
(env_prefix="GARAY_" + field name "gmail_sharimel" = "GARAY_GMAIL_SHARIMEL").
"""

from __future__ import annotations

import pytest

from garay.config.settings import Settings


def test_garay_gmail_sharimel_default_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default value is sharimelh@gmail.com when env var is not set."""
    monkeypatch.delenv("GARAY_GMAIL_SHARIMEL", raising=False)
    settings = Settings()
    assert settings.gmail_sharimel == "sharimelh@gmail.com"


def test_garay_gmail_sharimel_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """When GARAY_GMAIL_SHARIMEL is set in env, Settings reflects it."""
    monkeypatch.setenv("GARAY_GMAIL_SHARIMEL", "custom@example.com")
    settings = Settings()
    assert settings.gmail_sharimel == "custom@example.com"
