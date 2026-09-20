"""Tests for handlers_divisiones.py — /resumen_divisiones ConversationHandler.

States 310-313, group=13, callback prefix rep_s:.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from garay.aplicacion.socios.split import ResumenSocioPeriodo, ResumenSplitPeriodo
from garay.dominio.comun.dinero import Dinero

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_update_command(user_id: int = 99999) -> MagicMock:
    update = MagicMock()
    update.callback_query = None
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat = MagicMock()
    update.effective_chat.id = user_id
    update.effective_message = AsyncMock()
    msg = AsyncMock()
    msg.reply_text = AsyncMock()
    update.message = msg
    return update


def _make_update_cb(data: str, user_id: int = 99999) -> MagicMock:
    update = MagicMock()
    update.message = None
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat = MagicMock()
    update.effective_chat.id = user_id
    update.effective_message = AsyncMock()
    cq = AsyncMock()
    cq.data = data
    cq.answer = AsyncMock()
    cq.edit_message_text = AsyncMock()
    cq.edit_message_reply_markup = AsyncMock()
    cq.message = AsyncMock()
    cq.message.reply_text = AsyncMock()
    update.callback_query = cq
    return update


def _make_context(
    *,
    user_data: dict | None = None,
    split_service: MagicMock | None = None,
    propietario_ids: str = "99999",
    dev_ids: str = "",
) -> MagicMock:
    context = MagicMock()
    context.bot = AsyncMock()
    context.user_data = user_data if user_data is not None else {}
    if split_service is None:
        split_service = MagicMock()
        split_service.calcular_periodo.return_value = _empty_resultado()
    context.bot_data = {
        "split_socios_service": split_service,
        "freelancer_repo": MagicMock(),
    }
    return context


def _make_settings_patch(propietario_ids: str = "99999", dev_ids: str = "") -> MagicMock:
    settings = MagicMock()
    settings.propietario_telegram_ids = propietario_ids
    settings.dev_telegram_ids = dev_ids
    return settings


def _empty_resultado() -> ResumenSplitPeriodo:
    return ResumenSplitPeriodo(
        por_socio=(),
        total_agencia=Dinero(0),
        total_bruto=Dinero(0),
        total_comisiones_freelancer=Dinero(0),
        ventas_count=0,
    )


def _resultado_con_datos() -> ResumenSplitPeriodo:
    socios = (
        ResumenSocioPeriodo(nombre="empresa", porcentaje=Decimal("50"), acumulado=Dinero(500_000)),
        ResumenSocioPeriodo(nombre="garay", porcentaje=Decimal("25"), acumulado=Dinero(250_000)),
        ResumenSocioPeriodo(nombre="ryan", porcentaje=Decimal("25"), acumulado=Dinero(250_000)),
    )
    return ResumenSplitPeriodo(
        por_socio=socios,
        total_agencia=Dinero(1_000_000),
        total_bruto=Dinero(3_000_000),
        total_comisiones_freelancer=Dinero(400_000),
        ventas_count=3,
    )


# ---------------------------------------------------------------------------
# State constants (imported from implementation once it exists)
# ---------------------------------------------------------------------------


class TestStateConstants:
    """D4: verify state integers are 310-313."""

    def test_state_constants_defined(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_CAL_DESDE,
            DIV_CAL_HASTA,
            DIV_MENU,
            DIV_RESULT,
        )

        assert DIV_MENU == 310
        assert DIV_CAL_DESDE == 311
        assert DIV_CAL_HASTA == 312
        assert DIV_RESULT == 313


# ---------------------------------------------------------------------------
# Menu keyboard — toggle checkbox layout
# ---------------------------------------------------------------------------


class TestMenuKeyboard:
    """Menu shows Hoy, Ayer, Período, Cancelar in row 1 and Ver resumen in row 2."""

    @pytest.mark.asyncio
    async def test_menu_keyboard_row1_has_four_buttons(self) -> None:
        from unittest.mock import patch

        from garay.infraestructura.telegram.handlers_divisiones import (
            cmd_resumen_divisiones,
        )

        update = _make_update_command()
        context = _make_context()

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_patch("99999"),
        ):
            await cmd_resumen_divisiones(update, context)

        update.effective_message.reply_text.assert_called_once()
        call_kwargs = update.effective_message.reply_text.call_args
        markup = call_kwargs.kwargs.get("reply_markup") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert markup is not None, "reply_markup must be set"
        # Row 0: 4 buttons (Hoy, Ayer, Periodo, Cancelar)
        assert len(markup.inline_keyboard[0]) == 4

    @pytest.mark.asyncio
    async def test_menu_keyboard_row2_is_ver_resumen(self) -> None:
        from unittest.mock import patch

        from garay.infraestructura.telegram.handlers_divisiones import (
            cmd_resumen_divisiones,
        )

        update = _make_update_command()
        context = _make_context()

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_patch("99999"),
        ):
            await cmd_resumen_divisiones(update, context)

        markup = update.effective_message.reply_text.call_args.kwargs.get("reply_markup")
        if markup is None:
            markup = update.effective_message.reply_text.call_args.args[1]
        # Row 1 (second row): 1 button — Ver resumen
        assert len(markup.inline_keyboard) == 2
        assert len(markup.inline_keyboard[1]) == 1
        assert markup.inline_keyboard[1][0].callback_data == "rep_s:menu:ver"

    @pytest.mark.asyncio
    async def test_menu_initial_state_shows_unchecked_hoy_ayer(self) -> None:
        from unittest.mock import patch

        from garay.infraestructura.telegram.handlers_divisiones import (
            cmd_resumen_divisiones,
        )

        update = _make_update_command()
        context = _make_context()

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_patch("99999"),
        ):
            await cmd_resumen_divisiones(update, context)

        markup = update.effective_message.reply_text.call_args.kwargs.get("reply_markup")
        if markup is None:
            markup = update.effective_message.reply_text.call_args.args[1]
        hoy_btn = markup.inline_keyboard[0][0]
        ayer_btn = markup.inline_keyboard[0][1]
        assert "⬜" in hoy_btn.text
        assert "⬜" in ayer_btn.text

    @pytest.mark.asyncio
    async def test_menu_initializes_selection_flags_to_false(self) -> None:
        from unittest.mock import patch

        from garay.infraestructura.telegram.handlers_divisiones import (
            cmd_resumen_divisiones,
        )

        update = _make_update_command()
        context = _make_context()

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_patch("99999"),
        ):
            await cmd_resumen_divisiones(update, context)

        assert context.user_data.get("div_hoy_sel") is False
        assert context.user_data.get("div_ayer_sel") is False

    @pytest.mark.asyncio
    async def test_menu_button_callbacks_use_rep_s_prefix(self) -> None:
        from unittest.mock import patch

        from garay.infraestructura.telegram.handlers_divisiones import (
            cmd_resumen_divisiones,
        )

        update = _make_update_command()
        context = _make_context()

        with patch(
            "garay.infraestructura.telegram.auth.obtener_settings",
            return_value=_make_settings_patch("99999"),
        ):
            await cmd_resumen_divisiones(update, context)

        markup = update.effective_message.reply_text.call_args.kwargs.get("reply_markup")
        if markup is None:
            markup = update.effective_message.reply_text.call_args.args[1]
        flat_data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert all(d.startswith("rep_s:") for d in flat_data)


# ---------------------------------------------------------------------------
# _teclado_menu helper
# ---------------------------------------------------------------------------


class TestTecladoMenu:
    """_teclado_menu builds the correct toggle keyboard."""

    def test_teclado_menu_unchecked_shows_empty_boxes(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _teclado_menu

        markup = _teclado_menu(hoy_sel=False, ayer_sel=False)
        hoy_btn = markup.inline_keyboard[0][0]
        ayer_btn = markup.inline_keyboard[0][1]
        assert "⬜" in hoy_btn.text
        assert "⬜" in ayer_btn.text

    def test_teclado_menu_hoy_checked_shows_checkmark(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _teclado_menu

        markup = _teclado_menu(hoy_sel=True, ayer_sel=False)
        hoy_btn = markup.inline_keyboard[0][0]
        ayer_btn = markup.inline_keyboard[0][1]
        assert "✅" in hoy_btn.text
        assert "⬜" in ayer_btn.text

    def test_teclado_menu_both_checked(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _teclado_menu

        markup = _teclado_menu(hoy_sel=True, ayer_sel=True)
        hoy_btn = markup.inline_keyboard[0][0]
        ayer_btn = markup.inline_keyboard[0][1]
        assert "✅" in hoy_btn.text
        assert "✅" in ayer_btn.text

    def test_teclado_menu_has_two_rows(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _teclado_menu

        markup = _teclado_menu(hoy_sel=False, ayer_sel=False)
        assert len(markup.inline_keyboard) == 2

    def test_teclado_menu_row2_is_full_width_ver_resumen(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _teclado_menu

        markup = _teclado_menu(hoy_sel=False, ayer_sel=False)
        assert len(markup.inline_keyboard[1]) == 1
        assert markup.inline_keyboard[1][0].callback_data == "rep_s:menu:ver"

    def test_teclado_menu_callback_data_correct(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _teclado_menu

        markup = _teclado_menu(hoy_sel=False, ayer_sel=False)
        row0 = markup.inline_keyboard[0]
        assert row0[0].callback_data == "rep_s:menu:hoy"
        assert row0[1].callback_data == "rep_s:menu:ayer"
        assert row0[2].callback_data == "rep_s:menu:periodo"
        assert row0[3].callback_data == "rep_s:menu:cancel"


# ---------------------------------------------------------------------------
# Hoy / Ayer toggle behavior
# ---------------------------------------------------------------------------


class TestHoyAyerToggle:
    """Hoy and Ayer buttons toggle selection, do NOT immediately produce a result."""

    @pytest.mark.asyncio
    async def test_hoy_toggle_on_updates_keyboard_and_stays_in_div_menu(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_MENU,
            handle_div_menu,
        )

        context = _make_context(user_data={"div_hoy_sel": False, "div_ayer_sel": False})
        update = _make_update_cb("rep_s:menu:hoy")

        result = await handle_div_menu(update, context)

        assert result == DIV_MENU
        assert context.user_data["div_hoy_sel"] is True
        # Must edit the keyboard, not the text
        update.callback_query.edit_message_reply_markup.assert_called_once()
        # Must NOT call calcular_periodo
        context.bot_data["split_socios_service"].calcular_periodo.assert_not_called()

    @pytest.mark.asyncio
    async def test_hoy_toggle_off_when_already_selected(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_MENU,
            handle_div_menu,
        )

        context = _make_context(user_data={"div_hoy_sel": True, "div_ayer_sel": False})
        update = _make_update_cb("rep_s:menu:hoy")

        result = await handle_div_menu(update, context)

        assert result == DIV_MENU
        assert context.user_data["div_hoy_sel"] is False

    @pytest.mark.asyncio
    async def test_ayer_toggle_on_updates_keyboard_and_stays_in_div_menu(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_MENU,
            handle_div_menu,
        )

        context = _make_context(user_data={"div_hoy_sel": False, "div_ayer_sel": False})
        update = _make_update_cb("rep_s:menu:ayer")

        result = await handle_div_menu(update, context)

        assert result == DIV_MENU
        assert context.user_data["div_ayer_sel"] is True
        update.callback_query.edit_message_reply_markup.assert_called_once()
        context.bot_data["split_socios_service"].calcular_periodo.assert_not_called()

    @pytest.mark.asyncio
    async def test_ayer_toggle_off_when_already_selected(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_MENU,
            handle_div_menu,
        )

        context = _make_context(user_data={"div_hoy_sel": False, "div_ayer_sel": True})
        update = _make_update_cb("rep_s:menu:ayer")

        result = await handle_div_menu(update, context)

        assert result == DIV_MENU
        assert context.user_data["div_ayer_sel"] is False

    @pytest.mark.asyncio
    async def test_hoy_toggle_renders_checked_keyboard(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_menu

        context = _make_context(user_data={"div_hoy_sel": False, "div_ayer_sel": False})
        update = _make_update_cb("rep_s:menu:hoy")

        await handle_div_menu(update, context)

        call = update.callback_query.edit_message_reply_markup.call_args
        markup = call.kwargs.get("reply_markup") or (call.args[0] if call.args else None)
        assert markup is not None
        hoy_btn = markup.inline_keyboard[0][0]
        assert "✅" in hoy_btn.text


# ---------------------------------------------------------------------------
# Ver resumen — validation and computation
# ---------------------------------------------------------------------------


class TestVerResumen:
    """Ver resumen computes date range from selections or shows toast if none."""

    @pytest.mark.asyncio
    async def test_ver_resumen_with_nothing_selected_shows_toast_and_stays(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_MENU,
            handle_div_menu,
        )

        context = _make_context(user_data={"div_hoy_sel": False, "div_ayer_sel": False})
        update = _make_update_cb("rep_s:menu:ver")

        result = await handle_div_menu(update, context)

        assert result == DIV_MENU
        # Must show toast with show_alert=True
        cq = update.callback_query
        # answer() called with show_alert=True
        alert_calls = [
            c for c in cq.answer.call_args_list
            if c.kwargs.get("show_alert") is True or (len(c.args) > 0 and c.args[0])
        ]
        # At minimum one answer call with show_alert=True
        assert any(
            c.kwargs.get("show_alert") is True
            for c in cq.answer.call_args_list
        ), "Expected show_alert=True toast"
        context.bot_data["split_socios_service"].calcular_periodo.assert_not_called()

    @pytest.mark.asyncio
    async def test_ver_resumen_hoy_only_calls_calcular_with_today_today(self) -> None:
        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.handlers_divisiones import handle_div_menu

        split_service = MagicMock()
        split_service.calcular_periodo.return_value = _resultado_con_datos()
        context = _make_context(
            split_service=split_service,
            user_data={"div_hoy_sel": True, "div_ayer_sel": False},
        )
        update = _make_update_cb("rep_s:menu:ver")

        result = await handle_div_menu(update, context)

        assert result == ConversationHandler.END
        today = datetime.date.today()
        split_service.calcular_periodo.assert_called_once_with(today, today)

    @pytest.mark.asyncio
    async def test_ver_resumen_ayer_only_calls_calcular_with_yesterday_yesterday(self) -> None:
        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.handlers_divisiones import handle_div_menu

        split_service = MagicMock()
        split_service.calcular_periodo.return_value = _empty_resultado()
        context = _make_context(
            split_service=split_service,
            user_data={"div_hoy_sel": False, "div_ayer_sel": True},
        )
        update = _make_update_cb("rep_s:menu:ver")

        result = await handle_div_menu(update, context)

        assert result == ConversationHandler.END
        ayer = datetime.date.today() - datetime.timedelta(days=1)
        split_service.calcular_periodo.assert_called_once_with(ayer, ayer)

    @pytest.mark.asyncio
    async def test_ver_resumen_both_selected_calls_calcular_with_yesterday_today(self) -> None:
        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.handlers_divisiones import handle_div_menu

        split_service = MagicMock()
        split_service.calcular_periodo.return_value = _resultado_con_datos()
        context = _make_context(
            split_service=split_service,
            user_data={"div_hoy_sel": True, "div_ayer_sel": True},
        )
        update = _make_update_cb("rep_s:menu:ver")

        result = await handle_div_menu(update, context)

        assert result == ConversationHandler.END
        today = datetime.date.today()
        ayer = today - datetime.timedelta(days=1)
        split_service.calcular_periodo.assert_called_once_with(ayer, today)

    @pytest.mark.asyncio
    async def test_ver_resumen_edits_message_with_result(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_menu

        split_service = MagicMock()
        split_service.calcular_periodo.return_value = _resultado_con_datos()
        context = _make_context(
            split_service=split_service,
            user_data={"div_hoy_sel": True, "div_ayer_sel": False},
        )
        update = _make_update_cb("rep_s:menu:ver")

        await handle_div_menu(update, context)

        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_ver_resumen_sin_datos_edits_message(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_menu

        split_service = MagicMock()
        split_service.calcular_periodo.return_value = _empty_resultado()
        context = _make_context(
            split_service=split_service,
            user_data={"div_hoy_sel": True, "div_ayer_sel": False},
        )
        update = _make_update_cb("rep_s:menu:ver")

        await handle_div_menu(update, context)

        cq = update.callback_query
        cq.edit_message_text.assert_called_once()
        call = cq.edit_message_text.call_args
        text = call.args[0] if call.args else call.kwargs.get("text", "")
        assert "No hay datos" in text


# ---------------------------------------------------------------------------
# Calendar — end-before-start rejection
# ---------------------------------------------------------------------------


class TestCalendarValidation:
    """End date before start date is rejected inline."""

    @pytest.mark.asyncio
    async def test_end_before_start_is_rejected(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_dia

        start = datetime.date(2026, 9, 10)
        context = _make_context(
            user_data={"div_desde": start, "div_mes": "2026-09"}
        )
        # User picks 2026-09-05, which is before start 2026-09-10
        update = _make_update_cb("rep_s:dia:hasta:2026-09-05")

        await handle_div_dia(update, context)

        cq = update.callback_query
        # answer() called twice: initial ack (no args) + error toast (with message)
        assert cq.answer.call_count == 2
        last_call = cq.answer.call_args
        answer_text = last_call.args[0] if last_call.args else last_call.kwargs.get("text", "")
        assert "anterior" in answer_text.lower() or "fin" in answer_text.lower()


# ---------------------------------------------------------------------------
# Calendar — Atrás from DIV_CAL_HASTA returns to DIV_CAL_DESDE
# ---------------------------------------------------------------------------


class TestCalendarAtras:
    """Atrás from hasta step returns to desde step."""

    @pytest.mark.asyncio
    async def test_atras_from_hasta_returns_to_desde_state(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_CAL_DESDE,
            handle_div_atras,
        )

        context = _make_context(
            user_data={"div_desde": datetime.date(2026, 9, 1), "div_mes": "2026-09"}
        )
        update = _make_update_cb("rep_s:atras:hasta")

        result = await handle_div_atras(update, context)

        assert result == DIV_CAL_DESDE


# ---------------------------------------------------------------------------
# Calendar — month navigation
# ---------------------------------------------------------------------------


class TestCalendarMonthNav:
    """Month navigation re-renders the grid."""

    @pytest.mark.asyncio
    async def test_month_nav_prev_renders_correct_month(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_cal

        context = _make_context(user_data={"div_mes": "2026-09"})
        update = _make_update_cb("rep_s:cal:desde:2026-08")

        await handle_div_cal(update, context)

        cq = update.callback_query
        cq.edit_message_text.assert_called_once()
        # Verify month state updated
        assert context.user_data.get("div_mes") == "2026-08"


# ---------------------------------------------------------------------------
# Cancel button
# ---------------------------------------------------------------------------


class TestCancelButton:
    """Cancel ends the conversation."""

    @pytest.mark.asyncio
    async def test_cancel_edits_message_and_ends(self) -> None:
        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.handlers_divisiones import handle_div_menu

        split_service = MagicMock()
        context = _make_context(split_service=split_service)
        update = _make_update_cb("rep_s:menu:cancel")

        result = await handle_div_menu(update, context)

        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_called_once()


# ---------------------------------------------------------------------------
# _teclado_calendario helper
# ---------------------------------------------------------------------------


class TestTecladoCalendario:
    """_teclado_calendario returns a valid PTB InlineKeyboardMarkup."""

    def test_teclado_calendario_has_day_buttons(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _teclado_calendario

        markup = _teclado_calendario(2026, 9, "desde")
        flat = [btn for row in markup.inline_keyboard for btn in row]
        # September 2026 has 30 days + nav + back button
        day_buttons = [b for b in flat if b.callback_data.startswith("rep_s:dia:desde:")]
        assert len(day_buttons) == 30

    def test_teclado_calendario_has_nav_buttons(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _teclado_calendario

        markup = _teclado_calendario(2026, 9, "desde")
        flat = [btn for row in markup.inline_keyboard for btn in row]
        nav_buttons = [b for b in flat if b.callback_data.startswith("rep_s:cal:")]
        assert len(nav_buttons) >= 1

    def test_teclado_calendario_has_atras_button(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _teclado_calendario

        markup = _teclado_calendario(2026, 9, "desde")
        flat = [btn for row in markup.inline_keyboard for btn in row]
        atras_buttons = [b for b in flat if b.callback_data.startswith("rep_s:atras:")]
        assert len(atras_buttons) == 1


# ---------------------------------------------------------------------------
# build_divisiones_conv_handler factory
# ---------------------------------------------------------------------------


class TestConvHandlerFactory:
    """build_divisiones_conv_handler returns a ConversationHandler."""

    def test_factory_returns_conversation_handler(self) -> None:
        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.handlers_divisiones import (
            build_divisiones_conv_handler,
        )

        handler = build_divisiones_conv_handler()
        assert isinstance(handler, ConversationHandler)
