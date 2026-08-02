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
def mock_correo_repo() -> MagicMock:
    repo = MagicMock()
    repo.guardar.return_value = None
    repo.existe_referencia.return_value = False
    return repo


@pytest.fixture()
def mock_notificador() -> MagicMock:
    notificador = MagicMock()
    notificador.notificar.return_value = None
    return notificador


@pytest.fixture()
def client(
    mock_ingreso_repo: MagicMock,
    mock_egreso_repo: MagicMock,
    mock_correo_repo: MagicMock,
    mock_notificador: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("GARAY_FORWARD_EMAIL_SECRET", _SECRET)
    monkeypatch.setenv("GARAY_MONEDA_PREDETERMINADA", "COP")
    monkeypatch.setenv("GARAY_DEV_TELEGRAM_IDS", "")
    monkeypatch.setenv("GARAY_GRUPO_ID", "")
    monkeypatch.setenv("GARAY_TELEGRAM_BOT_TOKEN", "")
    import garay.config.settings as _settings_mod

    _settings_mod.obtener_settings.cache_clear()
    app = crear_app(
        ingreso_repo=mock_ingreso_repo,
        egreso_repo=mock_egreso_repo,
        correo_repo=mock_correo_repo,
        notificador=mock_notificador,
    )
    yield TestClient(app)
    _settings_mod.obtener_settings.cache_clear()
