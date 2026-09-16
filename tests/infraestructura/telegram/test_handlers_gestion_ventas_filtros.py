"""Tests for /gestionar_ventas date-filter flow (GV_FILTRO + GV_RANGO_INPUT).

New states: GV_FILTRO (227), GV_RANGO_INPUT (228).
New entry flow: /gestionar_ventas → filter screen → GV_FILTRO.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.infraestructura.telegram.handlers_gestion_ventas import (
    GV_FILTRO,
    GV_RANGO_INPUT,
    GV_SELECCIONAR,
    cmd_gestionar_ventas,
    handle_gv_filtro,
    handle_gv_rango_input,
    handle_gv_seleccionar_atras,
)

# ---------------------------------------------------------------------------
# Helpers (mirror the pattern from test_handlers_gestion_ventas.py)
# ---------------------------------------------------------------------------


def _make_venta(
    venta_id: uuid.UUID | None = None,
    registrado_en: datetime.datetime | None = None,
) -> MagicMock:
    v = MagicMock()
    v.id = venta_id or uuid.uuid4()
    v.cliente_id = uuid.uuid4()
    v.servicio_ids = [uuid.uuid4()]
    v.fecha = datetime.date(2026, 8, 1)
    v.registrado_en = registrado_en
    v.valor_venta = MagicMock()
    v.valor_venta.monto = 500_000
    v.participantes = MagicMock()
    v.participantes.vendedor_nombre = "Ana"
    v.participantes.cerrador_nombre = "Luis"
    return v


def _make_update(
    callback_data: str | None = None,
    text: str | None = None,
    user_id: int = 123,
) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    if callback_data is not None:
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
        update.message = None
    elif text is not None:
        update.callback_query = None
        update.message = MagicMock()
        update.message.text = text
    else:
        update.callback_query = None
        update.message = None
    return update


def _make_context(
    ventas: list[MagicMock] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}

    venta_repo = MagicMock()
    ventas_list = ventas if ventas is not None else [_make_venta()]
    venta_repo.listar_para_gestion.return_value = ventas_list

    freelancer_repo = MagicMock()
    freelancer = MagicMock()
    freelancer.es_admin = True
    freelancer.nombre = "Admin"
    freelancer_repo.buscar_por_telegram_id.return_value = freelancer

    ctx.bot_data = {
        "venta_repo": venta_repo,
        "freelancer_repo": freelancer_repo,
        "cliente_repo": MagicMock(),
        "servicio_repo": MagicMock(),
        "anular_venta_service": MagicMock(),
        "editar_fecha_venta_service": MagicMock(),
        "editar_cliente_venta_service": MagicMock(),
        "notificador": MagicMock(),
        "grupo_id": "-1001234567",
    }
    return ctx


def _extract_buttons_from_reply(update: MagicMock) -> list[Any]:
    """Flatten InlineKeyboardMarkup from reply_text call."""
    markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
    return [btn for row in markup.inline_keyboard for btn in row]


def _extract_buttons_from_edit(update: MagicMock) -> list[Any]:
    """Flatten InlineKeyboardMarkup from edit_message_text call."""
    markup = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
    return [btn for row in markup.inline_keyboard for btn in row]


# ---------------------------------------------------------------------------
# Test 1: entry shows filter screen (GV_FILTRO)
# ---------------------------------------------------------------------------


class TestEntryMuestraFiltros:
    @pytest.mark.asyncio
    async def test_entry_muestra_filtros_y_retorna_gv_filtro(self) -> None:
        """Entry point must show the filter screen and return GV_FILTRO, not load ventas."""
        update = _make_update()
        ctx = _make_context()

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            result = await cmd_gestionar_ventas(update, ctx)

        assert result == GV_FILTRO
        # Must NOT query repo at entry — waits for filter selection
        ctx.bot_data["venta_repo"].listar_para_gestion.assert_not_called()

    @pytest.mark.asyncio
    async def test_entry_muestra_4_botones_de_filtro_mas_cancelar(self) -> None:
        """Filter screen must include 5 buttons: 4 filter options + cancel."""
        update = _make_update()
        ctx = _make_context()

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            await cmd_gestionar_ventas(update, ctx)

        buttons = _extract_buttons_from_reply(update)
        callback_datas = [b.callback_data for b in buttons]
        assert "gv_f_7d" in callback_datas
        assert "gv_f_mes" in callback_datas
        assert "gv_f_mes_ant" in callback_datas
        assert "gv_f_rango" in callback_datas
        assert "gv_cancelar" in callback_datas

    @pytest.mark.asyncio
    async def test_entry_limpiar_no_llama_repo(self) -> None:
        """After _limpiar at entry, gv_desde/gv_hasta must be cleared (no stale state)."""
        update = _make_update()
        ctx = _make_context()
        ctx.user_data["gv_desde"] = "2026-01-01"
        ctx.user_data["gv_hasta"] = "2026-06-30"

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=MagicMock(dev_telegram_ids="", propietario_telegram_ids=""),
        ):
            await cmd_gestionar_ventas(update, ctx)

        assert "gv_desde" not in ctx.user_data
        assert "gv_hasta" not in ctx.user_data


# ---------------------------------------------------------------------------
# Test 2: gv_f_7d loads ventas list
# ---------------------------------------------------------------------------


class TestFiltro7Dias:
    @pytest.mark.asyncio
    async def test_filtro_7dias_retorna_gv_seleccionar(self) -> None:
        """gv_f_7d must load ventas and return GV_SELECCIONAR."""
        update = _make_update(callback_data="gv_f_7d")
        ctx = _make_context()

        result = await handle_gv_filtro(update, ctx)

        assert result == GV_SELECCIONAR

    @pytest.mark.asyncio
    async def test_filtro_7dias_llama_repo(self) -> None:
        """gv_f_7d must call listar_para_gestion with hoy - 7 days."""
        import garay.infraestructura.telegram.handlers_gestion_ventas as _mod

        today = datetime.date(2026, 9, 15)
        expected_desde = today - datetime.timedelta(days=7)

        update = _make_update(callback_data="gv_f_7d")
        ctx = _make_context()

        with patch.object(_mod.datetime, "date", wraps=datetime.date) as mock_date:  # type: ignore[attr-defined]
            mock_date.today.return_value = today
            result = await handle_gv_filtro(update, ctx)

        assert result == GV_SELECCIONAR
        ctx.bot_data["venta_repo"].listar_para_gestion.assert_called_once_with(expected_desde)

    @pytest.mark.asyncio
    async def test_filtro_7dias_guarda_desde_hasta_en_user_data(self) -> None:
        """gv_f_7d must store gv_desde and gv_hasta in user_data."""
        update = _make_update(callback_data="gv_f_7d")
        ctx = _make_context()

        await handle_gv_filtro(update, ctx)

        assert "gv_desde" in ctx.user_data
        assert "gv_hasta" in ctx.user_data


# ---------------------------------------------------------------------------
# Test 3: gv_f_mes uses first day of current month
# ---------------------------------------------------------------------------


class TestFiltroMesActual:
    @pytest.mark.asyncio
    async def test_filtro_mes_actual_usa_primer_dia_del_mes(self) -> None:
        """gv_f_mes must call listar_para_gestion with the first day of the current month."""
        import garay.infraestructura.telegram.handlers_gestion_ventas as _mod

        today = datetime.date(2026, 9, 15)
        expected_desde = datetime.date(2026, 9, 1)

        update = _make_update(callback_data="gv_f_mes")
        ctx = _make_context()

        with patch.object(_mod.datetime, "date", wraps=datetime.date) as mock_date:  # type: ignore[attr-defined]
            mock_date.today.return_value = today
            result = await handle_gv_filtro(update, ctx)

        assert result == GV_SELECCIONAR
        ctx.bot_data["venta_repo"].listar_para_gestion.assert_called_once_with(expected_desde)

    @pytest.mark.asyncio
    async def test_filtro_mes_actual_retorna_gv_seleccionar(self) -> None:
        update = _make_update(callback_data="gv_f_mes")
        ctx = _make_context()

        result = await handle_gv_filtro(update, ctx)

        assert result == GV_SELECCIONAR


# ---------------------------------------------------------------------------
# Test 4: gv_f_rango asks for text input
# ---------------------------------------------------------------------------


class TestFiltroRangoPideTexto:
    @pytest.mark.asyncio
    async def test_filtro_rango_pide_texto_y_retorna_gv_rango_input(self) -> None:
        """gv_f_rango must show text prompt and return GV_RANGO_INPUT."""
        update = _make_update(callback_data="gv_f_rango")
        ctx = _make_context()

        result = await handle_gv_filtro(update, ctx)

        assert result == GV_RANGO_INPUT
        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_filtro_rango_no_llama_repo(self) -> None:
        """gv_f_rango must NOT call the repo — waits for user text."""
        update = _make_update(callback_data="gv_f_rango")
        ctx = _make_context()

        await handle_gv_filtro(update, ctx)

        ctx.bot_data["venta_repo"].listar_para_gestion.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: GV_RANGO_INPUT — invalid text stays in state
# ---------------------------------------------------------------------------


class TestRangoInputInvalido:
    @pytest.mark.asyncio
    async def test_rango_invalido_repregunta(self) -> None:
        """Invalid text must reply an error and remain in GV_RANGO_INPUT."""
        update = _make_update(text="esto no es un rango")
        ctx = _make_context()

        result = await handle_gv_rango_input(update, ctx)

        assert result == GV_RANGO_INPUT

    @pytest.mark.asyncio
    async def test_rango_invalido_solo_una_fecha(self) -> None:
        """A single date (no separator) is invalid — stays in GV_RANGO_INPUT."""
        update = _make_update(text="15/08/2026")
        ctx = _make_context()

        result = await handle_gv_rango_input(update, ctx)

        assert result == GV_RANGO_INPUT

    @pytest.mark.asyncio
    async def test_rango_invalido_avisa_al_usuario(self) -> None:
        """Invalid input must reply something to the user."""
        update = _make_update(text="basura")
        ctx = _make_context()

        await handle_gv_rango_input(update, ctx)

        update.effective_message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# Test 6: GV_RANGO_INPUT — valid text parses and loads list
# ---------------------------------------------------------------------------


class TestRangoInputValido:
    @pytest.mark.asyncio
    async def test_rango_valido_retorna_gv_seleccionar(self) -> None:
        """Valid range '01/08/2026 - 15/09/2026' must return GV_SELECCIONAR."""
        update = _make_update(text="01/08/2026 - 15/09/2026")
        ctx = _make_context()

        result = await handle_gv_rango_input(update, ctx)

        assert result == GV_SELECCIONAR

    @pytest.mark.asyncio
    async def test_rango_valido_llama_repo_con_desde(self) -> None:
        """Valid range must call listar_para_gestion with the 'desde' date."""
        update = _make_update(text="01/08/2026 - 15/09/2026")
        ctx = _make_context()

        await handle_gv_rango_input(update, ctx)

        expected_desde = datetime.date(2026, 8, 1)
        ctx.bot_data["venta_repo"].listar_para_gestion.assert_called_once_with(expected_desde)

    @pytest.mark.asyncio
    async def test_rango_valido_guarda_desde_hasta(self) -> None:
        """Valid range must store gv_desde and gv_hasta in user_data."""
        update = _make_update(text="01/08/2026 - 15/09/2026")
        ctx = _make_context()

        await handle_gv_rango_input(update, ctx)

        assert ctx.user_data.get("gv_desde") == "2026-08-01"
        assert ctx.user_data.get("gv_hasta") == "2026-09-15"

    @pytest.mark.asyncio
    async def test_rango_valido_filtra_client_side_por_hasta(self) -> None:
        """ventas whose registrado_en > hasta must be excluded (client-side filter)."""
        dentro = _make_venta(registrado_en=datetime.datetime(2026, 9, 10))
        fuera = _make_venta(registrado_en=datetime.datetime(2026, 9, 20))  # beyond hasta

        update = _make_update(text="01/08/2026 - 15/09/2026")
        ctx = _make_context(ventas=[dentro, fuera])

        await handle_gv_rango_input(update, ctx)

        # Text-input path uses reply_text (no callback_query to edit).
        markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        # Only the "dentro" venta should appear
        assert f"gv_sel:{dentro.id}" in callbacks
        assert f"gv_sel:{fuera.id}" not in callbacks


# ---------------------------------------------------------------------------
# Test 7: venta list markup includes gv_atras button
# ---------------------------------------------------------------------------


class TestListaTieneBotonAtras:
    @pytest.mark.asyncio
    async def test_lista_tiene_boton_atras_en_filtro_7d(self) -> None:
        """The ventas list shown after gv_f_7d must have an 'Atrás' button (gv_atras)."""
        update = _make_update(callback_data="gv_f_7d")
        ctx = _make_context()

        await handle_gv_filtro(update, ctx)

        markup = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "gv_atras" in callbacks

    @pytest.mark.asyncio
    async def test_lista_tiene_boton_cancelar_en_filtro_7d(self) -> None:
        """The ventas list shown after gv_f_7d must have a 'Cancelar' button."""
        update = _make_update(callback_data="gv_f_7d")
        ctx = _make_context()

        await handle_gv_filtro(update, ctx)

        markup = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "gv_cancelar" in callbacks

    @pytest.mark.asyncio
    async def test_lista_tiene_boton_atras_en_rango_valido(self) -> None:
        """The ventas list shown after a valid rango must also have an 'Atrás' button."""
        update = _make_update(text="01/08/2026 - 15/09/2026")
        ctx = _make_context()

        await handle_gv_rango_input(update, ctx)

        # Text-input path uses reply_text.
        markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "gv_atras" in callbacks


# ---------------------------------------------------------------------------
# Test 8: gv_atras from GV_SELECCIONAR returns GV_FILTRO
# ---------------------------------------------------------------------------


class TestAtrasDesdeListaVuelveAFiltros:
    @pytest.mark.asyncio
    async def test_atras_desde_lista_retorna_gv_filtro(self) -> None:
        """gv_atras callback in GV_SELECCIONAR must return GV_FILTRO."""
        update = _make_update(callback_data="gv_atras")
        ctx = _make_context()

        result = await handle_gv_seleccionar_atras(update, ctx)

        assert result == GV_FILTRO

    @pytest.mark.asyncio
    async def test_atras_desde_lista_muestra_pantalla_filtros(self) -> None:
        """gv_atras from list must show the filter screen with filter buttons."""
        update = _make_update(callback_data="gv_atras")
        ctx = _make_context()

        await handle_gv_seleccionar_atras(update, ctx)

        update.callback_query.edit_message_text.assert_called_once()
        markup = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "gv_f_7d" in callbacks
        assert "gv_f_mes" in callbacks
        assert "gv_f_mes_ant" in callbacks
        assert "gv_f_rango" in callbacks


# ---------------------------------------------------------------------------
# Misc: mes anterior
# ---------------------------------------------------------------------------


class TestFiltroMesAnterior:
    @pytest.mark.asyncio
    async def test_filtro_mes_anterior_usa_rango_correcto(self) -> None:
        """gv_f_mes_ant must use first and last day of the previous month."""
        import garay.infraestructura.telegram.handlers_gestion_ventas as _mod

        today = datetime.date(2026, 9, 15)
        # Previous month: August 2026 -> 01/08/2026 - 31/08/2026
        expected_desde = datetime.date(2026, 8, 1)

        update = _make_update(callback_data="gv_f_mes_ant")
        ctx = _make_context()

        with patch.object(_mod.datetime, "date", wraps=datetime.date) as mock_date:  # type: ignore[attr-defined]
            mock_date.today.return_value = today
            result = await handle_gv_filtro(update, ctx)

        assert result == GV_SELECCIONAR
        ctx.bot_data["venta_repo"].listar_para_gestion.assert_called_once_with(expected_desde)

    @pytest.mark.asyncio
    async def test_filtro_mes_anterior_guarda_hasta_ultimo_dia(self) -> None:
        """gv_f_mes_ant must store gv_hasta as the last day of the previous month."""
        import garay.infraestructura.telegram.handlers_gestion_ventas as _mod

        today = datetime.date(2026, 9, 15)
        # August 2026 has 31 days
        expected_hasta = datetime.date(2026, 8, 31)

        update = _make_update(callback_data="gv_f_mes_ant")
        ctx = _make_context()

        with patch.object(_mod.datetime, "date", wraps=datetime.date) as mock_date:  # type: ignore[attr-defined]
            mock_date.today.return_value = today
            await handle_gv_filtro(update, ctx)

        stored_hasta = datetime.date.fromisoformat(ctx.user_data["gv_hasta"])
        assert stored_hasta == expected_hasta


# ---------------------------------------------------------------------------
# Client-side hasta filter for gv_f_7d
# ---------------------------------------------------------------------------


class TestClienteSideHastaFilter:
    @pytest.mark.asyncio
    async def test_filtro_7d_excluye_ventas_fuera_del_rango(self) -> None:
        """ventas with registrado_en beyond 'hasta' must be filtered out client-side."""
        import garay.infraestructura.telegram.handlers_gestion_ventas as _mod

        today = datetime.date(2026, 9, 15)

        dentro = _make_venta(registrado_en=datetime.datetime(2026, 9, 14))
        fuera = _make_venta(registrado_en=datetime.datetime(2026, 9, 20))  # beyond today

        update = _make_update(callback_data="gv_f_7d")
        ctx = _make_context(ventas=[dentro, fuera])

        with patch.object(_mod.datetime, "date", wraps=datetime.date) as mock_date:  # type: ignore[attr-defined]
            mock_date.today.return_value = today
            await handle_gv_filtro(update, ctx)

        markup = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert f"gv_sel:{dentro.id}" in callbacks
        assert f"gv_sel:{fuera.id}" not in callbacks

    @pytest.mark.asyncio
    async def test_venta_sin_registrado_en_no_se_filtra(self) -> None:
        """ventas with registrado_en=None must NOT be filtered out (uncertain, keep them)."""
        venta = _make_venta(registrado_en=None)

        update = _make_update(callback_data="gv_f_7d")
        ctx = _make_context(ventas=[venta])

        await handle_gv_filtro(update, ctx)

        markup = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert f"gv_sel:{venta.id}" in callbacks
