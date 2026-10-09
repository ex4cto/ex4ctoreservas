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


# ---------------------------------------------------------------------------
# ResumenVentaDetalle button label format
# ---------------------------------------------------------------------------


class TestButtonLabelFormat:
    """Button label format: {dd/mm}  {primer_nombre}  ${k_format}."""

    def test_k_format_600k(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _fmt_k

        assert _fmt_k(600_000) == "$600k"

    def test_k_format_1200k(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _fmt_k

        assert _fmt_k(1_200_000) == "$1.200k"

    def test_k_format_2500k(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import _fmt_k

        assert _fmt_k(2_500_000) == "$2.500k"

    def test_venta_button_label_format(self) -> None:
        """Button label uses dd/mm, first name, k-format."""
        import uuid

        from garay.aplicacion.socios.split import ResumenFreelancerPeriodo, ResumenVentaDetalle
        from garay.infraestructura.telegram.handlers_divisiones import _venta_btn_label

        detalle = ResumenVentaDetalle(
            venta_id=uuid.uuid4(),
            fecha=datetime.date(2026, 9, 19),
            vendedor_nombre="Juan García",
            cerrador_nombre=None,
            valor_bruto=Dinero(600_000),
            desglose_vendedor=Dinero(60_000),
            desglose_cerrador=Dinero(0),
            desglose_punto=Dinero(0),
            desglose_agencia=Dinero(540_000),
            split_socios=(),
        )
        label = _venta_btn_label(detalle)
        assert label == "19/09  Juan  $600k"

    def test_venta_button_label_none_vendedor_shows_dash(self) -> None:
        import uuid

        from garay.aplicacion.socios.split import ResumenVentaDetalle
        from garay.infraestructura.telegram.handlers_divisiones import _venta_btn_label

        detalle = ResumenVentaDetalle(
            venta_id=uuid.uuid4(),
            fecha=datetime.date(2026, 9, 19),
            vendedor_nombre=None,
            cerrador_nombre=None,
            valor_bruto=Dinero(1_200_000),
            desglose_vendedor=Dinero(0),
            desglose_cerrador=Dinero(0),
            desglose_punto=Dinero(0),
            desglose_agencia=Dinero(1_200_000),
            split_socios=(),
        )
        label = _venta_btn_label(detalle)
        assert label == "19/09  —  $1.200k"


# ---------------------------------------------------------------------------
# Result view with sale buttons — handle_div_resultado
# ---------------------------------------------------------------------------


def _resultado_con_detalle() -> "ResumenSplitPeriodo":
    """ResumenSplitPeriodo with ventas_detalle populated."""
    import uuid

    from garay.aplicacion.socios.split import (
        ResumenFreelancerPeriodo,
        ResumenVentaDetalle,
    )

    socios = (
        ResumenSocioPeriodo(nombre="empresa", porcentaje=Decimal("50"), acumulado=Dinero(500_000)),
        ResumenSocioPeriodo(nombre="garay", porcentaje=Decimal("25"), acumulado=Dinero(250_000)),
        ResumenSocioPeriodo(nombre="ryan", porcentaje=Decimal("25"), acumulado=Dinero(250_000)),
    )
    venta1 = ResumenVentaDetalle(
        venta_id=uuid.uuid4(),
        fecha=datetime.date(2026, 9, 19),
        vendedor_nombre="Juan García",
        cerrador_nombre=None,
        valor_bruto=Dinero(600_000),
        desglose_vendedor=Dinero(60_000),
        desglose_cerrador=Dinero(0),
        desglose_punto=Dinero(0),
        desglose_agencia=Dinero(540_000),
        split_socios=socios,
    )
    freelancers = (
        ResumenFreelancerPeriodo(nombre="Juan García", comision=Dinero(60_000)),
    )
    return ResumenSplitPeriodo(
        por_socio=socios,
        total_agencia=Dinero(540_000),
        total_bruto=Dinero(600_000),
        total_comisiones_freelancer=Dinero(60_000),
        ventas_count=1,
        ventas_detalle=(venta1,),
        por_freelancer=freelancers,
    )


class TestResultViewWithButtons:
    """When result has ventas_detalle, show inline keyboard with sale buttons."""

    @pytest.mark.asyncio
    async def test_ver_resultado_shows_sale_buttons(self) -> None:
        """Ver resumen produces inline keyboard with one button per sale."""
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_menu

        split_service = MagicMock()
        split_service.calcular_periodo.return_value = _resultado_con_detalle()
        context = _make_context(
            split_service=split_service,
            user_data={"div_hoy_sel": True, "div_ayer_sel": False},
        )
        update = _make_update_cb("rep_s:menu:ver")

        await handle_div_menu(update, context)

        cq = update.callback_query
        cq.edit_message_text.assert_called_once()
        call = cq.edit_message_text.call_args
        markup = call.kwargs.get("reply_markup")
        assert markup is not None, "Should have reply_markup with sale buttons"
        # One button per sale
        flat = [btn for row in markup.inline_keyboard for btn in row]
        sale_btns = [b for b in flat if b.callback_data.startswith("rep_s:venta:")]
        assert len(sale_btns) == 1

    @pytest.mark.asyncio
    async def test_ver_resultado_stores_ventas_in_user_data(self) -> None:
        """Ventas list stored in user_data[div_ventas] for drill-down access."""
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_menu

        split_service = MagicMock()
        split_service.calcular_periodo.return_value = _resultado_con_detalle()
        context = _make_context(
            split_service=split_service,
            user_data={"div_hoy_sel": True, "div_ayer_sel": False},
        )
        update = _make_update_cb("rep_s:menu:ver")

        await handle_div_menu(update, context)

        assert "div_ventas" in context.user_data
        assert len(context.user_data["div_ventas"]) == 1

    @pytest.mark.asyncio
    async def test_ver_resultado_returns_div_result_state(self) -> None:
        """When result has sales, handler returns DIV_RESULT (not END)."""
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_RESULT,
            handle_div_menu,
        )

        split_service = MagicMock()
        split_service.calcular_periodo.return_value = _resultado_con_detalle()
        context = _make_context(
            split_service=split_service,
            user_data={"div_hoy_sel": True, "div_ayer_sel": False},
        )
        update = _make_update_cb("rep_s:menu:ver")

        result = await handle_div_menu(update, context)

        assert result == DIV_RESULT


# ---------------------------------------------------------------------------
# Drill-down per-sale handler
# ---------------------------------------------------------------------------


class TestDrillDownVenta:
    """handle_div_venta renders per-sale detail and shows Atrás button."""

    @pytest.mark.asyncio
    async def test_drill_down_shows_detail_text(self) -> None:
        import uuid

        from garay.aplicacion.socios.split import ResumenVentaDetalle
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_RESULT,
            handle_div_venta,
        )

        venta = ResumenVentaDetalle(
            venta_id=uuid.uuid4(),
            fecha=datetime.date(2026, 9, 19),
            vendedor_nombre="Juan García",
            cerrador_nombre=None,
            valor_bruto=Dinero(600_000),
            desglose_vendedor=Dinero(60_000),
            desglose_cerrador=Dinero(0),
            desglose_punto=Dinero(0),
            desglose_agencia=Dinero(540_000),
            split_socios=(),
        )
        context = _make_context(user_data={"div_ventas": [venta]})
        update = _make_update_cb("rep_s:venta:0")

        result = await handle_div_venta(update, context)

        assert result == DIV_RESULT
        cq = update.callback_query
        cq.edit_message_text.assert_called_once()
        call = cq.edit_message_text.call_args
        text = call.args[0] if call.args else call.kwargs.get("text", "")
        assert "Juan" in text or "19/09" in text

    @pytest.mark.asyncio
    async def test_drill_down_shows_atras_button(self) -> None:
        import uuid

        from garay.aplicacion.socios.split import ResumenVentaDetalle
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_venta

        venta = ResumenVentaDetalle(
            venta_id=uuid.uuid4(),
            fecha=datetime.date(2026, 9, 10),
            vendedor_nombre="Maria",
            cerrador_nombre=None,
            valor_bruto=Dinero(300_000),
            desglose_vendedor=Dinero(30_000),
            desglose_cerrador=Dinero(0),
            desglose_punto=Dinero(0),
            desglose_agencia=Dinero(270_000),
            split_socios=(),
        )
        context = _make_context(user_data={"div_ventas": [venta]})
        update = _make_update_cb("rep_s:venta:0")

        await handle_div_venta(update, context)

        cq = update.callback_query
        call = cq.edit_message_text.call_args
        markup = call.kwargs.get("reply_markup")
        assert markup is not None
        flat = [btn for row in markup.inline_keyboard for btn in row]
        atras = [b for b in flat if "atras" in b.callback_data]
        assert len(atras) == 1
        assert atras[0].callback_data == "rep_s:atras:resultado"


# ---------------------------------------------------------------------------
# Atrás from drill-down restores result view
# ---------------------------------------------------------------------------


class TestAtrasDesdeDrillDown:
    """Pressing Atrás in drill-down restores the result view with sale buttons."""

    @pytest.mark.asyncio
    async def test_atras_resultado_restores_result_state(self) -> None:
        import uuid

        from garay.aplicacion.socios.split import ResumenVentaDetalle
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_RESULT,
            handle_div_atras,
        )

        venta = ResumenVentaDetalle(
            venta_id=uuid.uuid4(),
            fecha=datetime.date(2026, 9, 19),
            vendedor_nombre="Pedro",
            cerrador_nombre=None,
            valor_bruto=Dinero(500_000),
            desglose_vendedor=Dinero(50_000),
            desglose_cerrador=Dinero(0),
            desglose_punto=Dinero(0),
            desglose_agencia=Dinero(450_000),
            split_socios=(),
        )

        from garay.aplicacion.socios.split import (
            ResumenFreelancerPeriodo,
            ResumenSplitPeriodo,
        )

        resultado = ResumenSplitPeriodo(
            por_socio=(),
            total_agencia=Dinero(450_000),
            total_bruto=Dinero(500_000),
            total_comisiones_freelancer=Dinero(50_000),
            ventas_count=1,
            ventas_detalle=(venta,),
            por_freelancer=(),
        )

        context = _make_context(user_data={
            "div_ventas": [venta],
            "div_resultado": resultado,
            "div_periodo_label": "Hoy (19/09/2026)",
        })
        update = _make_update_cb("rep_s:atras:resultado")

        result = await handle_div_atras(update, context)

        assert result == DIV_RESULT
        cq = update.callback_query
        cq.edit_message_text.assert_called_once()
        call = cq.edit_message_text.call_args
        markup = call.kwargs.get("reply_markup")
        assert markup is not None


# ---------------------------------------------------------------------------
# Bug Q — _venta_btn_label must show registrado_en date when available
# ---------------------------------------------------------------------------


class TestVentaBtnLabelRegistradoEn:
    def _make_detalle(
        self,
        fecha: datetime.date,
        registrado_en: datetime.datetime | None,
    ) -> object:
        from garay.aplicacion.socios.split import ResumenVentaDetalle
        from garay.dominio.comun.dinero import Dinero

        return ResumenVentaDetalle(
            venta_id=__import__("uuid").uuid4(),
            fecha=fecha,
            vendedor_nombre="Juan",
            cerrador_nombre=None,
            valor_bruto=Dinero(600_000),
            desglose_vendedor=Dinero(0),
            desglose_cerrador=Dinero(0),
            desglose_punto=Dinero(0),
            desglose_agencia=Dinero(0),
            split_socios=(),
            registrado_en=registrado_en,
        )

    def test_label_uses_registrado_en_date_when_set(self) -> None:
        """When registrado_en is set, the button label must show that date, not fecha."""
        from garay.infraestructura.telegram.handlers_divisiones import _venta_btn_label

        fecha = datetime.date(2026, 9, 10)          # tour date: 10/09
        reg = datetime.datetime(2026, 9, 1, 10, 0)  # registered: 01/09

        detalle = self._make_detalle(fecha=fecha, registrado_en=reg)
        label = _venta_btn_label(detalle)  # type: ignore[arg-type]

        assert "01/09" in label, f"Expected registration date 01/09 in label, got: {label}"
        assert "10/09" not in label, f"Tour date 10/09 must NOT appear when registrado_en is set"

    def test_label_falls_back_to_fecha_when_registrado_en_is_none(self) -> None:
        """When registrado_en is None, the label must fall back to fecha."""
        from garay.infraestructura.telegram.handlers_divisiones import _venta_btn_label

        fecha = datetime.date(2026, 9, 10)

        detalle = self._make_detalle(fecha=fecha, registrado_en=None)
        label = _venta_btn_label(detalle)  # type: ignore[arg-type]

        assert "10/09" in label, f"Expected tour date 10/09 as fallback, got: {label}"


# ---------------------------------------------------------------------------
# Liquidaciones — ✅ marker in freelancer list (Change 1)
# ---------------------------------------------------------------------------


def _make_liq_context(
    *,
    user_data: dict | None = None,
    liquidar_service: MagicMock | None = None,
    pago_repo: MagicMock | None = None,
    resultado: object | None = None,
) -> MagicMock:
    """Build a context with liquidar_service and pago_freelancer_repo in bot_data."""
    import uuid

    from garay.aplicacion.liquidaciones.servicio import LiquidarFreelancerService
    from garay.aplicacion.socios.split import ResumenFreelancerPeriodo, ResumenSplitPeriodo
    from garay.dominio.comun.dinero import Dinero

    freelancer_repo = MagicMock()
    fl_id = uuid.uuid4()
    mock_fl = MagicMock()
    mock_fl.nombre = "Ana López"
    mock_fl.id = fl_id
    freelancer_repo.listar_activos.return_value = [mock_fl]

    if resultado is None:
        freelancers = (ResumenFreelancerPeriodo(nombre="Ana López", comision=Dinero(100_000)),)
        resultado = ResumenSplitPeriodo(
            por_socio=(),
            total_agencia=Dinero(500_000),
            total_bruto=Dinero(600_000),
            total_comisiones_freelancer=Dinero(100_000),
            ventas_count=1,
            ventas_detalle=(),
            por_freelancer=freelancers,
        )

    if pago_repo is None:
        pago_repo = MagicMock()
        pago_repo.buscar_solapados.return_value = []

    if liquidar_service is None:
        liquidar_service = MagicMock(spec=LiquidarFreelancerService)

    desde = datetime.date(2026, 9, 1)
    hasta = datetime.date(2026, 9, 30)
    default_user_data = {
        "div_resultado": resultado,
        "div_liq_desde": desde,
        "div_liq_hasta": hasta,
        "div_periodo_label": "Septiembre 2026",
    }
    if user_data is not None:
        default_user_data.update(user_data)

    context = MagicMock()
    context.bot = AsyncMock()
    context.user_data = default_user_data
    context.bot_data = {
        "split_socios_service": MagicMock(),
        "freelancer_repo": freelancer_repo,
        "liquidar_service": liquidar_service,
        "pago_freelancer_repo": pago_repo,
    }
    return context, fl_id  # type: ignore[return-value]


def _make_pago_freelancer(
    fl_id: "uuid.UUID",
    monto: int = 100_000,
    fecha_pago: datetime.datetime | None = None,
    registrado_por_nombre: str | None = "Admin",
) -> object:
    import uuid as _uuid

    from garay.dominio.comun.dinero import Dinero
    from garay.dominio.liquidaciones.entidades import PagoFreelancer

    return PagoFreelancer(
        id=_uuid.uuid4(),
        freelancer_id=fl_id,
        monto=Dinero(monto),
        desde=datetime.date(2026, 9, 1),
        hasta=datetime.date(2026, 9, 30),
        fecha_pago=fecha_pago or datetime.datetime(2026, 9, 15, 10, 0),
        registrado_por_telegram_id=1,
        registrado_por_nombre=registrado_por_nombre,
    )


class TestLiqFreelancerListMarker:
    """handle_div_liq_start adds ✅ prefix when freelancer already has a payment."""

    @pytest.mark.asyncio
    async def test_freelancer_without_payment_shows_no_checkmark(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_LIQ_FREELANCER,
            handle_div_liq_start,
        )

        context, fl_id = _make_liq_context()
        # pago_repo returns empty → not yet paid
        context.bot_data["pago_freelancer_repo"].buscar_solapados.return_value = []

        update = _make_update_cb("rep_s:liq:start")
        result = await handle_div_liq_start(update, context)

        assert result == DIV_LIQ_FREELANCER
        cq = update.callback_query
        cq.edit_message_text.assert_called_once()
        markup = cq.edit_message_text.call_args.kwargs.get("reply_markup")
        assert markup is not None
        fl_buttons = [
            btn
            for row in markup.inline_keyboard
            for btn in row
            if btn.callback_data.startswith("rep_s:liq:fl:")
        ]
        assert len(fl_buttons) == 1
        # No checkmark prefix
        assert not fl_buttons[0].text.startswith("✅ ")

    @pytest.mark.asyncio
    async def test_freelancer_with_payment_shows_checkmark(self) -> None:
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_LIQ_FREELANCER,
            handle_div_liq_start,
        )

        context, fl_id = _make_liq_context()
        pago = _make_pago_freelancer(fl_id)
        context.bot_data["pago_freelancer_repo"].buscar_solapados.return_value = [pago]

        update = _make_update_cb("rep_s:liq:start")
        result = await handle_div_liq_start(update, context)

        assert result == DIV_LIQ_FREELANCER
        markup = update.callback_query.edit_message_text.call_args.kwargs.get("reply_markup")
        fl_buttons = [
            btn
            for row in markup.inline_keyboard
            for btn in row
            if btn.callback_data.startswith("rep_s:liq:fl:")
        ]
        assert len(fl_buttons) == 1
        assert fl_buttons[0].text.startswith("✅ ")

    @pytest.mark.asyncio
    async def test_freelancer_list_works_when_pago_repo_missing(self) -> None:
        """Graceful degradation: no ✅ marker when pago_freelancer_repo not in bot_data."""
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_LIQ_FREELANCER,
            handle_div_liq_start,
        )

        context, fl_id = _make_liq_context()
        del context.bot_data["pago_freelancer_repo"]

        update = _make_update_cb("rep_s:liq:start")
        result = await handle_div_liq_start(update, context)

        assert result == DIV_LIQ_FREELANCER
        markup = update.callback_query.edit_message_text.call_args.kwargs.get("reply_markup")
        fl_buttons = [
            btn
            for row in markup.inline_keyboard
            for btn in row
            if btn.callback_data.startswith("rep_s:liq:fl:")
        ]
        assert len(fl_buttons) == 1
        assert not fl_buttons[0].text.startswith("✅ ")


# ---------------------------------------------------------------------------
# Liquidaciones — ya liquidado screen (Change 2)
# ---------------------------------------------------------------------------


def _make_liq_resultado(
    fl_id: "uuid.UUID",
    solapados: list | None = None,
) -> object:
    import uuid as _uuid

    from garay.aplicacion.liquidaciones.servicio import (
        ComisionVentaDetalle,
        ResultadoCalculoLiquidacion,
    )
    from garay.dominio.comun.dinero import Dinero

    desglose_item = ComisionVentaDetalle(
        fecha=datetime.date(2026, 9, 10),
        servicio_nombre="City Tour",
        adultos=2,
        ninos=0,
        comision=Dinero(100_000),
    )
    return ResultadoCalculoLiquidacion(
        freelancer_id=fl_id,
        freelancer_nombre="Ana López",
        freelancer_telegram_id=None,
        desde=datetime.date(2026, 9, 1),
        hasta=datetime.date(2026, 9, 30),
        comisiones_total=Dinero(100_000),
        desglose=[desglose_item],
        solapados=solapados if solapados is not None else [],
    )


class TestLiqYaLiquidadoScreen:
    """handle_div_liq_freelancer shows read-only screen when solapados is non-empty."""

    @pytest.mark.asyncio
    async def test_con_solapados_muestra_pantalla_ya_liquidado(self) -> None:
        import uuid

        from garay.aplicacion.liquidaciones.servicio import LiquidarFreelancerService
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_LIQ_CONFIRMAR,
            handle_div_liq_freelancer,
        )

        fl_id = uuid.uuid4()
        pago = _make_pago_freelancer(fl_id)
        liq_resultado = _make_liq_resultado(fl_id, solapados=[pago])

        liquidar_service = MagicMock(spec=LiquidarFreelancerService)
        liquidar_service.calcular.return_value = liq_resultado

        context, _ = _make_liq_context(liquidar_service=liquidar_service)
        update = _make_update_cb(f"rep_s:liq:fl:{fl_id}")

        result = await handle_div_liq_freelancer(update, context)

        assert result == DIV_LIQ_CONFIRMAR
        cq = update.callback_query
        cq.edit_message_text.assert_called_once()
        call_args = cq.edit_message_text.call_args
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        assert "ya fue liquidado" in text

    @pytest.mark.asyncio
    async def test_con_solapados_muestra_boton_anular_y_atras(self) -> None:
        import uuid

        from garay.aplicacion.liquidaciones.servicio import LiquidarFreelancerService
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_liq_freelancer

        fl_id = uuid.uuid4()
        pago = _make_pago_freelancer(fl_id)
        liq_resultado = _make_liq_resultado(fl_id, solapados=[pago])

        liquidar_service = MagicMock(spec=LiquidarFreelancerService)
        liquidar_service.calcular.return_value = liq_resultado

        context, _ = _make_liq_context(liquidar_service=liquidar_service)
        update = _make_update_cb(f"rep_s:liq:fl:{fl_id}")

        await handle_div_liq_freelancer(update, context)

        markup = update.callback_query.edit_message_text.call_args.kwargs.get("reply_markup")
        assert markup is not None
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        # One anular button + one Atrás button
        assert len(all_buttons) == 2
        anular_btns = [b for b in all_buttons if b.callback_data.startswith("rep_s:liq:anular:")]
        assert len(anular_btns) == 1
        assert all_buttons[-1].callback_data == "rep_s:liq:atras_confirmar"
        # No Confirmar button
        assert not any(btn.callback_data.startswith("rep_s:liq:confirmar:") for btn in all_buttons)

    @pytest.mark.asyncio
    async def test_con_solapados_muestra_fecha_y_registrador(self) -> None:
        import uuid

        from garay.aplicacion.liquidaciones.servicio import LiquidarFreelancerService
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_liq_freelancer

        fl_id = uuid.uuid4()
        pago = _make_pago_freelancer(
            fl_id,
            fecha_pago=datetime.datetime(2026, 9, 15, 10, 0),
            registrado_por_nombre="María",
        )
        liq_resultado = _make_liq_resultado(fl_id, solapados=[pago])

        liquidar_service = MagicMock(spec=LiquidarFreelancerService)
        liquidar_service.calcular.return_value = liq_resultado

        context, _ = _make_liq_context(liquidar_service=liquidar_service)
        update = _make_update_cb(f"rep_s:liq:fl:{fl_id}")

        await handle_div_liq_freelancer(update, context)

        call_args = update.callback_query.edit_message_text.call_args
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        assert "15/09/2026" in text
        assert "María" in text

    @pytest.mark.asyncio
    async def test_sin_solapados_muestra_pantalla_confirmacion(self) -> None:
        import uuid

        from garay.aplicacion.liquidaciones.servicio import LiquidarFreelancerService
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_LIQ_CONFIRMAR,
            handle_div_liq_freelancer,
        )

        fl_id = uuid.uuid4()
        liq_resultado = _make_liq_resultado(fl_id, solapados=[])

        liquidar_service = MagicMock(spec=LiquidarFreelancerService)
        liquidar_service.calcular.return_value = liq_resultado

        context, _ = _make_liq_context(liquidar_service=liquidar_service)
        update = _make_update_cb(f"rep_s:liq:fl:{fl_id}")

        result = await handle_div_liq_freelancer(update, context)

        assert result == DIV_LIQ_CONFIRMAR
        call_args = update.callback_query.edit_message_text.call_args
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        # Confirmation screen title
        assert "Confirmar liquidación" in text or "liquidaci" in text.lower()

    @pytest.mark.asyncio
    async def test_sin_solapados_muestra_boton_confirmar(self) -> None:
        import uuid

        from garay.aplicacion.liquidaciones.servicio import LiquidarFreelancerService
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_liq_freelancer

        fl_id = uuid.uuid4()
        liq_resultado = _make_liq_resultado(fl_id, solapados=[])

        liquidar_service = MagicMock(spec=LiquidarFreelancerService)
        liquidar_service.calcular.return_value = liq_resultado

        context, _ = _make_liq_context(liquidar_service=liquidar_service)
        update = _make_update_cb(f"rep_s:liq:fl:{fl_id}")

        await handle_div_liq_freelancer(update, context)

        markup = update.callback_query.edit_message_text.call_args.kwargs.get("reply_markup")
        assert markup is not None
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        confirm_btns = [b for b in all_buttons if b.callback_data.startswith("rep_s:liq:confirmar:")]
        assert len(confirm_btns) == 1

    @pytest.mark.asyncio
    async def test_multiples_solapados_tienen_boton_anular_individual(self) -> None:
        """Each solapado gets its own anular button row, Atrás is last."""
        import uuid

        from garay.aplicacion.liquidaciones.servicio import LiquidarFreelancerService
        from garay.infraestructura.telegram.handlers_divisiones import handle_div_liq_freelancer

        fl_id = uuid.uuid4()
        pago1 = _make_pago_freelancer(fl_id, monto=100_000)
        pago2 = _make_pago_freelancer(fl_id, monto=200_000)
        liq_resultado = _make_liq_resultado(fl_id, solapados=[pago1, pago2])

        liquidar_service = MagicMock(spec=LiquidarFreelancerService)
        liquidar_service.calcular.return_value = liq_resultado

        context, _ = _make_liq_context(liquidar_service=liquidar_service)
        update = _make_update_cb(f"rep_s:liq:fl:{fl_id}")

        await handle_div_liq_freelancer(update, context)

        markup = update.callback_query.edit_message_text.call_args.kwargs.get("reply_markup")
        assert markup is not None
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        anular_btns = [b for b in all_buttons if b.callback_data.startswith("rep_s:liq:anular:")]
        assert len(anular_btns) == 2
        # Each anular button references a different pago id
        pago_ids = {str(pago1.id), str(pago2.id)}
        for btn in anular_btns:
            btn_pago_id = btn.callback_data[len("rep_s:liq:anular:"):]
            assert btn_pago_id in pago_ids
        # Atrás is last
        assert all_buttons[-1].callback_data == "rep_s:liq:atras_confirmar"


# ---------------------------------------------------------------------------
# Liquidaciones — anular pago flow
# ---------------------------------------------------------------------------


class TestAnularPagoFlow:
    """handle_div_liq_confirmar handles anular callbacks correctly."""

    @pytest.mark.asyncio
    async def test_anular_muestra_pantalla_confirmacion(self) -> None:
        """rep_s:liq:anular:{uuid} shows confirmation screen with two buttons."""
        import uuid

        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_LIQ_CONFIRMAR,
            handle_div_liq_confirmar,
        )

        fl_id = uuid.uuid4()
        pago = _make_pago_freelancer(fl_id)
        liq_resultado = _make_liq_resultado(fl_id, solapados=[pago])

        context, _ = _make_liq_context()
        context.user_data["div_liq_resultado"] = liq_resultado

        update = _make_update_cb(f"rep_s:liq:anular:{pago.id}")
        result = await handle_div_liq_confirmar(update, context)

        assert result == DIV_LIQ_CONFIRMAR
        cq = update.callback_query
        cq.edit_message_text.assert_called_once()
        call_args = cq.edit_message_text.call_args
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        assert "Anular" in text or "anular" in text.lower()
        markup = call_args.kwargs.get("reply_markup")
        assert markup is not None
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        ok_btns = [b for b in all_buttons if b.callback_data.startswith("rep_s:liq:anular_ok:")]
        cancel_btns = [b for b in all_buttons if b.callback_data == "rep_s:liq:anular_cancelar"]
        assert len(ok_btns) == 1
        assert len(cancel_btns) == 1

    @pytest.mark.asyncio
    async def test_anular_ok_llama_eliminar_y_regresa_lista(self) -> None:
        """rep_s:liq:anular_ok:{uuid} deletes the pago and re-renders the freelancer list."""
        import uuid

        from garay.aplicacion.liquidaciones.servicio import LiquidarFreelancerService
        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_LIQ_FREELANCER,
            handle_div_liq_confirmar,
        )

        fl_id = uuid.uuid4()
        pago = _make_pago_freelancer(fl_id)
        liq_resultado = _make_liq_resultado(fl_id, solapados=[pago])

        pago_repo = MagicMock()
        pago_repo.buscar_solapados.return_value = []

        liquidar_service = MagicMock(spec=LiquidarFreelancerService)

        context, _ = _make_liq_context(
            pago_repo=pago_repo, liquidar_service=liquidar_service
        )
        context.user_data["div_liq_resultado"] = liq_resultado

        update = _make_update_cb(f"rep_s:liq:anular_ok:{pago.id}")
        result = await handle_div_liq_confirmar(update, context)

        pago_repo.eliminar.assert_called_once_with(pago.id)
        assert result == DIV_LIQ_FREELANCER

    @pytest.mark.asyncio
    async def test_anular_cancelar_regresa_pantalla_ya_liquidado(self) -> None:
        """rep_s:liq:anular_cancelar re-renders the ya_liquidado screen."""
        import uuid

        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_LIQ_CONFIRMAR,
            handle_div_liq_confirmar,
        )

        fl_id = uuid.uuid4()
        pago = _make_pago_freelancer(fl_id)
        liq_resultado = _make_liq_resultado(fl_id, solapados=[pago])

        context, _ = _make_liq_context()
        context.user_data["div_liq_resultado"] = liq_resultado

        update = _make_update_cb("rep_s:liq:anular_cancelar")
        result = await handle_div_liq_confirmar(update, context)

        assert result == DIV_LIQ_CONFIRMAR
        cq = update.callback_query
        cq.edit_message_text.assert_called_once()
        call_args = cq.edit_message_text.call_args
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        assert "ya fue liquidado" in text
        markup = call_args.kwargs.get("reply_markup")
        assert markup is not None
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        anular_btns = [b for b in all_buttons if b.callback_data.startswith("rep_s:liq:anular:")]
        assert len(anular_btns) == 1
        assert all_buttons[-1].callback_data == "rep_s:liq:atras_confirmar"

    @pytest.mark.asyncio
    async def test_anular_uuid_invalido_retorna_estado_sin_crash(self) -> None:
        """rep_s:liq:anular:{bad} with invalid UUID returns DIV_LIQ_CONFIRMAR without crashing."""
        import uuid

        from garay.infraestructura.telegram.handlers_divisiones import (
            DIV_LIQ_CONFIRMAR,
            handle_div_liq_confirmar,
        )

        fl_id = uuid.uuid4()
        liq_resultado = _make_liq_resultado(fl_id, solapados=[])
        context, _ = _make_liq_context()
        context.user_data["div_liq_resultado"] = liq_resultado

        update = _make_update_cb("rep_s:liq:anular:not-a-uuid")
        result = await handle_div_liq_confirmar(update, context)

        assert result == DIV_LIQ_CONFIRMAR
