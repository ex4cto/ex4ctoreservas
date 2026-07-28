"""Unit tests for cmd_mis_ventas and cmd_resumen_empresa handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.infraestructura.telegram.handlers import cmd_mis_ventas, cmd_resumen_empresa


def _make_update(user_id: int = 123) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    return update


def _make_context(**bot_data_overrides: object) -> MagicMock:
    ctx = MagicMock()
    base: dict[str, object] = {}
    base.update(bot_data_overrides)
    ctx.bot_data = base
    return ctx


@pytest.mark.asyncio
async def test_cmd_mis_ventas_sin_repos() -> None:
    """Missing repos → reply error message, return early."""
    update = _make_update()
    # freelancer_repo present but venta_repo and comision_registrada_repo missing
    freelancer_repo = MagicMock()
    freelancer_mock = MagicMock()
    freelancer_mock.nombre = "Carlos"
    freelancer_repo.buscar_por_telegram_id.return_value = freelancer_mock
    context = _make_context(freelancer_repo=freelancer_repo)

    await cmd_mis_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]

    update.effective_message.reply_text.assert_called_once()
    call_args = update.effective_message.reply_text.call_args[0][0]
    assert "Error" in call_args or "error" in call_args


@pytest.mark.asyncio
async def test_cmd_mis_ventas_sin_ventas() -> None:
    """Empty ventas list → message mentions 0 ventas."""
    update = _make_update()

    freelancer_repo = MagicMock()
    freelancer_mock = MagicMock()
    freelancer_mock.nombre = "Carlos"
    freelancer_repo.buscar_por_telegram_id.return_value = freelancer_mock

    venta_repo = MagicMock()
    venta_repo.listar_por_freelancer_y_periodo.return_value = []

    comision_repo = MagicMock()
    comision_repo.listar_por_venta_ids.return_value = []

    context = _make_context(
        freelancer_repo=freelancer_repo,
        venta_repo=venta_repo,
        comision_registrada_repo=comision_repo,
    )

    await cmd_mis_ventas.__wrapped__(update, context)  # type: ignore[attr-defined]

    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "0" in msg


@pytest.mark.asyncio
async def test_cmd_resumen_empresa_no_repos() -> None:
    """Missing repos → reply error message."""
    update = _make_update()
    context = _make_context()  # no repos at all

    await cmd_resumen_empresa.__wrapped__(update, context)  # type: ignore[attr-defined]

    update.effective_message.reply_text.assert_called_once()
    call_args = update.effective_message.reply_text.call_args[0][0]
    assert "Error" in call_args or "error" in call_args
