"""Tests for #4: Cancelar + Atrás buttons in the editar-tour field menu."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.infraestructura.telegram.handlers_tours import (
    EDF_TOUR,
    _teclado_campos,
    handle_edt_ficha,
)


def test_teclado_campos_incluye_atras_y_cancelar() -> None:
    markup = _teclado_campos()
    datas = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "edt_atras" in datas
    assert "edt_cancelar_flujo" in datas


@pytest.mark.asyncio
async def test_atras_vuelve_a_la_lista_de_tours() -> None:
    srv = MagicMock()
    srv.categoria = "BARU"
    srv.activo = True
    srv.nombre = "Tour Playa"
    srv.id = uuid.uuid4()

    update = MagicMock()
    update.effective_message = AsyncMock()
    cq = AsyncMock()
    cq.data = "edt_atras"
    update.callback_query = cq

    ctx = MagicMock()
    ctx.user_data = {"edt_servicios": [srv], "edt_familia": "BARU"}
    ctx.bot_data = {}

    result = await handle_edt_ficha(update, ctx)

    assert result == EDF_TOUR
    update.effective_message.reply_text.assert_called_once()
    markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert any("Tour Playa" in lb for lb in labels)
