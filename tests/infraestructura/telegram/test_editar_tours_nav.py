"""Tests for #4: Cancelar + Atrás buttons in the editar-tour field menu."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.infraestructura.telegram.handlers_tours import (
    EDF_FAMILIA,
    EDF_TOUR,
    _teclado_campos,
    _teclado_tours,
    handle_edt_ficha,
    handle_edt_tour,
)


def _srv_mock(nombre: str = "Tour Playa", familia: str = "BARU", activo: bool = True) -> MagicMock:
    srv = MagicMock()
    srv.categoria = familia
    srv.activo = activo
    srv.nombre = nombre
    srv.id = uuid.uuid4()
    return srv


def test_teclado_campos_incluye_atras_y_cancelar() -> None:
    markup = _teclado_campos()
    datas = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "edt_atras" in datas
    assert "edt_cancelar_flujo" in datas


def test_atras_y_cancelar_usan_mensajes_centralizados() -> None:
    from garay.mensajes.catalogo import obtener_mensaje

    markup = _teclado_campos()
    etiqueta_por_data = {
        b.callback_data: b.text for row in markup.inline_keyboard for b in row
    }
    assert etiqueta_por_data["edt_atras"] == obtener_mensaje("tour_boton_atras")
    assert etiqueta_por_data["edt_cancelar_flujo"] == obtener_mensaje("tour_boton_cancelar")


def test_teclado_tours_incluye_atras_con_back_callback() -> None:
    markup = _teclado_tours([_srv_mock()], "BARU", "edt_tour:", back_callback="edt_volver_familias")
    datas = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "edt_volver_familias" in datas


def test_teclado_tours_atras_usa_mensaje_centralizado() -> None:
    from garay.mensajes.catalogo import obtener_mensaje

    markup = _teclado_tours([_srv_mock()], "BARU", "edt_tour:", back_callback="edt_volver_familias")
    etiqueta_por_data = {
        b.callback_data: b.text for row in markup.inline_keyboard for b in row
    }
    assert etiqueta_por_data["edt_volver_familias"] == obtener_mensaje("tour_boton_atras")


def test_teclado_tours_sin_back_callback_no_tiene_atras() -> None:
    markup = _teclado_tours([_srv_mock()], "BARU", "elt_tour:")
    datas = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "edt_volver_familias" not in datas


@pytest.mark.asyncio
async def test_atras_en_lista_de_tours_vuelve_a_familias() -> None:
    update = MagicMock()
    update.effective_message = AsyncMock()
    cq = AsyncMock()
    cq.data = "edt_volver_familias"
    update.callback_query = cq

    ctx = MagicMock()
    ctx.user_data = {"edt_servicios": [_srv_mock()], "edt_familia": "BARU"}
    ctx.bot_data = {}

    result = await handle_edt_tour(update, ctx)

    assert result == EDF_FAMILIA
    update.effective_message.reply_text.assert_called_once()
    markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
    datas = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert any(d.startswith("edt_familia:") for d in datas)


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
