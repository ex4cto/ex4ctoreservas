"""Shared fixtures for webhook infrastructure tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from garay.aplicacion.webhook.app import crear_app

_SECRET = "test-secret-12345"


@pytest.fixture()
def mock_ingreso_repo() -> MagicMock:
    repo = MagicMock()
    repo.existe_referencia.return_value = False
    return repo


@pytest.fixture()
def mock_egreso_repo() -> MagicMock:
    repo = MagicMock()
    repo.existe_referencia.return_value = False
    return repo


@pytest.fixture()
def client(
    mock_ingreso_repo: MagicMock,
    mock_egreso_repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("GARAY_FORWARD_EMAIL_SECRET", _SECRET)
    monkeypatch.setenv("GARAY_MONEDA_PREDETERMINADA", "COP")
    import garay.config.settings as _settings_mod

    _settings_mod.obtener_settings.cache_clear()
    app = crear_app(ingreso_repo=mock_ingreso_repo, egreso_repo=mock_egreso_repo)
    yield TestClient(app)
    _settings_mod.obtener_settings.cache_clear()
