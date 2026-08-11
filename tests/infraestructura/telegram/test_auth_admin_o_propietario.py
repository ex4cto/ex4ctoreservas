"""Unit tests for requiere_admin_o_propietario_conv decorator — RED phase (TDD B2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.infraestructura.telegram.auth import requiere_admin_o_propietario_conv


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


class TestRequiereAdminOPropietarioConv:
    @pytest.mark.asyncio
    async def test_dev_es_permitido(self) -> None:
        update = _make_update(user_id=999)
        ctx = _make_context()
        wrapped = requiere_admin_o_propietario_conv(_dummy)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(
                dev_telegram_ids="999",
                propietario_telegram_ids="",
            ),
        ):
            result = await wrapped(update, ctx)

        assert result == 42

    @pytest.mark.asyncio
    async def test_propietario_es_permitido(self) -> None:
        update = _make_update(user_id=111)
        ctx = _make_context()
        wrapped = requiere_admin_o_propietario_conv(_dummy)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(
                dev_telegram_ids="",
                propietario_telegram_ids="111,222",
            ),
        ):
            result = await wrapped(update, ctx)

        assert result == 42

    @pytest.mark.asyncio
    async def test_admin_freelancer_es_permitido(self) -> None:
        freelancer = MagicMock()
        freelancer.es_admin = True
        update = _make_update(user_id=200)
        ctx = _make_context(freelancer=freelancer)
        wrapped = requiere_admin_o_propietario_conv(_dummy)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(
                dev_telegram_ids="",
                propietario_telegram_ids="",
            ),
        ):
            result = await wrapped(update, ctx)

        assert result == 42

    @pytest.mark.asyncio
    async def test_freelancer_no_admin_es_denegado(self) -> None:
        freelancer = MagicMock()
        freelancer.es_admin = False
        update = _make_update(user_id=300)
        ctx = _make_context(freelancer=freelancer)
        wrapped = requiere_admin_o_propietario_conv(_dummy)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(
                dev_telegram_ids="",
                propietario_telegram_ids="",
            ),
        ):
            result = await wrapped(update, ctx)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_usuario_desconocido_es_denegado(self) -> None:
        update = _make_update(user_id=400)
        ctx = _make_context(freelancer=None)
        wrapped = requiere_admin_o_propietario_conv(_dummy)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(
                dev_telegram_ids="",
                propietario_telegram_ids="",
            ),
        ):
            result = await wrapped(update, ctx)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_effective_user_none_devuelve_end(self) -> None:
        update = _make_update(user_id=None)
        ctx = _make_context()
        wrapped = requiere_admin_o_propietario_conv(_dummy)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(
                dev_telegram_ids="",
                propietario_telegram_ids="",
            ),
        ):
            result = await wrapped(update, ctx)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_repo_ausente_devuelve_end(self) -> None:
        update = _make_update(user_id=500)
        ctx = MagicMock()
        ctx.bot_data = {}  # no freelancer_repo
        wrapped = requiere_admin_o_propietario_conv(_dummy)

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(
                dev_telegram_ids="",
                propietario_telegram_ids="",
            ),
        ):
            result = await wrapped(update, ctx)

        assert result == ConversationHandler.END
