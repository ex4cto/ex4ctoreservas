"""Unit tests for the standalone requiere_admin_o_propietario decorator.

Standalone CommandHandlers deny with ``None`` (not ``ConversationHandler.END``).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.infraestructura.telegram.auth import requiere_admin_o_propietario


def _make_update(user_id: int | None = 123) -> MagicMock:
    update = MagicMock()
    if user_id is None:
        update.effective_user = None
    else:
        update.effective_user = MagicMock()
        update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    return update


def _make_context(freelancer: MagicMock | None = None) -> MagicMock:
    ctx = MagicMock()
    repo = MagicMock()
    repo.buscar_por_telegram_id.return_value = freelancer
    ctx.bot_data = {"freelancer_repo": repo}
    return ctx


async def _dummy(update: object, context: object) -> int:
    return 42


def _settings(*, dev: str = "", propietario: str = "") -> MagicMock:
    return MagicMock(dev_telegram_ids=dev, propietario_telegram_ids=propietario)


class TestRequiereAdminOPropietarioStandalone:
    @pytest.mark.asyncio
    async def test_dev_es_permitido(self) -> None:
        wrapped = requiere_admin_o_propietario(_dummy)
        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_settings(dev="999"),
        ):
            result = await wrapped(_make_update(user_id=999), _make_context())
        assert result == 42

    @pytest.mark.asyncio
    async def test_propietario_es_permitido(self) -> None:
        wrapped = requiere_admin_o_propietario(_dummy)
        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_settings(propietario="111,222"),
        ):
            result = await wrapped(_make_update(user_id=111), _make_context())
        assert result == 42

    @pytest.mark.asyncio
    async def test_admin_freelancer_es_permitido(self) -> None:
        freelancer = MagicMock()
        freelancer.es_admin = True
        wrapped = requiere_admin_o_propietario(_dummy)
        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_settings(),
        ):
            result = await wrapped(
                _make_update(user_id=200), _make_context(freelancer=freelancer)
            )
        assert result == 42

    @pytest.mark.asyncio
    async def test_freelancer_no_admin_es_denegado(self) -> None:
        freelancer = MagicMock()
        freelancer.es_admin = False
        wrapped = requiere_admin_o_propietario(_dummy)
        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_settings(),
        ):
            result = await wrapped(
                _make_update(user_id=300), _make_context(freelancer=freelancer)
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_usuario_desconocido_es_denegado(self) -> None:
        wrapped = requiere_admin_o_propietario(_dummy)
        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_settings(),
        ):
            result = await wrapped(_make_update(user_id=400), _make_context(freelancer=None))
        assert result is None

    @pytest.mark.asyncio
    async def test_effective_user_none_es_denegado(self) -> None:
        wrapped = requiere_admin_o_propietario(_dummy)
        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_settings(),
        ):
            result = await wrapped(_make_update(user_id=None), _make_context())
        assert result is None

    @pytest.mark.asyncio
    async def test_repo_ausente_es_denegado(self) -> None:
        ctx = MagicMock()
        ctx.bot_data = {}  # no freelancer_repo
        wrapped = requiere_admin_o_propietario(_dummy)
        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_settings(),
        ):
            result = await wrapped(_make_update(user_id=500), ctx)
        assert result is None
