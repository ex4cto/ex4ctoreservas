"""Unit tests for cmd_verificar_pago handler."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Ingreso
from garay.infraestructura.telegram.handlers import cmd_verificar_pago

_UTC = datetime.UTC


def _make_ingreso(
    *,
    monto: str = "150000",
    banco: str = "Bancolombia",
    remitente: str | None = "JUAN GARCIA",
    minutos_atras: int = 3,
) -> Ingreso:
    now = datetime.datetime.now(_UTC)
    return Ingreso(
        id=uuid.uuid4(),
        banco=banco,
        monto=Dinero(monto),
        fecha=now.date(),
        referencia=f"REF-{uuid.uuid4().hex[:6]}",
        remitente=remitente,
        fecha_recibido=now - datetime.timedelta(minutes=minutos_atras),
    )


def _make_update() -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_message = AsyncMock()
    return update


def _make_context(**bot_data_overrides: object) -> MagicMock:
    ctx = MagicMock()
    base: dict[str, object] = {}
    base.update(bot_data_overrides)
    ctx.bot_data = base
    return ctx


@pytest.mark.asyncio
async def test_verificar_pago_con_pagos_responde_lista_formateada() -> None:
    """With recent ingresos, response lists each one formatted."""
    ingreso_a = _make_ingreso(
        monto="150000", banco="Bancolombia", remitente="JUAN GARCIA", minutos_atras=3
    )
    ingreso_b = _make_ingreso(
        monto="200000", banco="Nequi", remitente="MARIA LOPEZ", minutos_atras=1
    )

    ingreso_repo = MagicMock()
    ingreso_repo.listar_recientes.return_value = [ingreso_a, ingreso_b]

    update = _make_update()
    context = _make_context(ingreso_repo=ingreso_repo)

    await cmd_verificar_pago.__wrapped__(update, context)  # type: ignore[attr-defined]

    ingreso_repo.listar_recientes.assert_called_once_with(5)
    update.effective_message.reply_text.assert_called_once()

    msg: str = update.effective_message.reply_text.call_args[0][0]
    assert "150.000" in msg or "150,000" in msg
    assert "JUAN GARCIA" in msg
    assert "Bancolombia" in msg
    assert "200.000" in msg or "200,000" in msg
    assert "MARIA LOPEZ" in msg
    assert "Nequi" in msg


@pytest.mark.asyncio
async def test_verificar_pago_sin_pagos_responde_mensaje_vacio() -> None:
    """With no recent ingresos, response indicates no payments found."""
    ingreso_repo = MagicMock()
    ingreso_repo.listar_recientes.return_value = []

    update = _make_update()
    context = _make_context(ingreso_repo=ingreso_repo)

    await cmd_verificar_pago.__wrapped__(update, context)  # type: ignore[attr-defined]

    update.effective_message.reply_text.assert_called_once()
    msg: str = update.effective_message.reply_text.call_args[0][0]
    assert "Sin pagos" in msg or "sin pagos" in msg


@pytest.mark.asyncio
async def test_verificar_pago_sin_repo_responde_error_interno() -> None:
    """Missing ingreso_repo → reply error message."""
    update = _make_update()
    context = _make_context()  # no ingreso_repo

    await cmd_verificar_pago.__wrapped__(update, context)  # type: ignore[attr-defined]

    update.effective_message.reply_text.assert_called_once()
    msg: str = update.effective_message.reply_text.call_args[0][0]
    assert "error" in msg.lower() or "Error" in msg


@pytest.mark.asyncio
async def test_verificar_pago_formatea_hace_n_min_correctamente() -> None:
    """Time-ago string 'hace N min' appears in response."""
    ingreso = _make_ingreso(minutos_atras=4)

    ingreso_repo = MagicMock()
    ingreso_repo.listar_recientes.return_value = [ingreso]

    update = _make_update()
    context = _make_context(ingreso_repo=ingreso_repo)

    await cmd_verificar_pago.__wrapped__(update, context)  # type: ignore[attr-defined]

    msg: str = update.effective_message.reply_text.call_args[0][0]
    assert "min" in msg


@pytest.mark.asyncio
async def test_verificar_pago_remitente_none_no_rompe() -> None:
    """Ingreso with remitente=None should still render without crash."""
    ingreso = _make_ingreso(remitente=None, minutos_atras=2)

    ingreso_repo = MagicMock()
    ingreso_repo.listar_recientes.return_value = [ingreso]

    update = _make_update()
    context = _make_context(ingreso_repo=ingreso_repo)

    await cmd_verificar_pago.__wrapped__(update, context)  # type: ignore[attr-defined]

    update.effective_message.reply_text.assert_called_once()
