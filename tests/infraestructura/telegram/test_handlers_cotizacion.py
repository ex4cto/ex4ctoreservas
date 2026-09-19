"""Tests for handlers_cotizacion.py — SC-D*, SC-E*, SC-G*, SC-H*, SC-I*.

Groups covered:
  5A: Date picker states (SC-G01 to SC-G07)
  5B: /cancelar mid-flow (SC-H01, SC-H02, SC-H03)
  5C: Email delivery (SC-D01 to SC-D04)
  5D: Telegram notification (SC-E01 to SC-E06)
  5F: Happy path integration (SC-I01 to SC-I05)
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from garay.aplicacion.cotizacion.contexto import ContextoCotizacion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_update_cb(data: str) -> MagicMock:
    update = MagicMock()
    update.message = None
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.full_name = "Test User"
    update.effective_chat = MagicMock()
    update.effective_chat.id = 12345
    update.effective_message = AsyncMock()
    cq = AsyncMock()
    cq.data = data
    cq.answer = AsyncMock()
    cq.edit_message_text = AsyncMock()
    update.callback_query = cq
    return update


def _make_update_text(text: str) -> MagicMock:
    update = MagicMock()
    update.callback_query = None
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.full_name = "Test User"
    update.effective_chat = MagicMock()
    update.effective_chat.id = 12345
    update.effective_message = AsyncMock()
    msg = AsyncMock()
    msg.text = text
    msg.reply_text = AsyncMock()
    update.message = msg
    return update


def _make_update_command(cmd: str) -> MagicMock:
    update = MagicMock()
    update.callback_query = None
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.full_name = "Test User"
    update.effective_chat = MagicMock()
    update.effective_chat.id = 12345
    update.effective_message = AsyncMock()
    msg = AsyncMock()
    msg.text = cmd
    msg.reply_text = AsyncMock()
    update.message = msg
    return update


def _make_context(
    ctx: ContextoCotizacion | None = None,
    servicio_repo: MagicMock | None = None,
    notificador_email: MagicMock | None = None,
) -> MagicMock:
    from garay.aplicacion.cotizacion.servicio import GenerarCotizacionService

    context = MagicMock()
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()

    fl_repo = MagicMock()
    fl_repo.buscar_por_telegram_id.return_value = None  # fallback to full_name

    context.bot_data = {
        "freelancer_repo": fl_repo,
        "servicio_repo": servicio_repo or MagicMock(),
        "cotizacion_service": GenerarCotizacionService(),
        "notificador_email": notificador_email,
    }
    context.user_data = {}
    if ctx is not None:
        context.user_data["cotizacion_ctx"] = ctx
    return context


def _make_servicio(
    numero: int = 1,
    nombre: str = "Tour Test",
    precio_adulto: Decimal | None = Decimal("150000"),
    precio_nino: Decimal | None = Decimal("80000"),
    categoria: str = "BARU",
) -> MagicMock:
    import uuid

    svc = MagicMock()
    svc.id = uuid.uuid4()
    svc.numero = numero
    svc.nombre = nombre
    svc.precio_neto_adulto = precio_adulto
    svc.precio_neto_nino = precio_nino
    svc.categoria = categoria
    return svc


# ---------------------------------------------------------------------------
# TASK-5A: Date picker states (SC-G01 to SC-G07)
# ---------------------------------------------------------------------------


class TestDatePickerKeyboards:
    """SC-G01 / SC-G02: COT_FECHA has no back button; COT_FECHA_TEXTO has one."""

    @pytest.mark.asyncio
    async def test_cot_fecha_keyboard_has_no_back_button(self) -> None:
        """SC-G01: Initial date picker keyboard has no cot_fecha_volver button."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            _teclado_fecha_cotizacion,
        )

        markup = _teclado_fecha_cotizacion()
        flat_data = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "cot_fecha_volver" not in flat_data

    @pytest.mark.asyncio
    async def test_cot_fecha_texto_keyboard_has_back_button(self) -> None:
        """SC-G02: Sub-state keyboard HAS cot_fecha_volver back button."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            _teclado_fecha_texto_cotizacion,
        )

        markup = _teclado_fecha_texto_cotizacion()
        flat_data = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        assert "cot_fecha_volver" in flat_data


class TestDateResolution:
    """SC-G03 / SC-G04: Ayer / Antes de ayer resolve correctly."""

    @pytest.mark.asyncio
    async def test_ayer_resuelve_ayer(self) -> None:
        """SC-G03: 'ayer' callback sets fecha_salida to yesterday in Bogota."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            COT_IDIOMA,
            handle_cot_ayer,
        )

        ctx = ContextoCotizacion()
        update = _make_update_cb("cot_ayer")
        context = _make_context(ctx=ctx)

        mocked_date = datetime.date(2026, 9, 20)
        with patch(
            "garay.infraestructura.telegram.handlers_cotizacion._hoy_bogota",
            return_value=mocked_date,
        ):
            result = await handle_cot_ayer(update, context)

        assert result == COT_IDIOMA
        salida = context.user_data["cotizacion_ctx"].fecha_salida
        assert salida is not None
        assert salida.date() == datetime.date(2026, 9, 19)

    @pytest.mark.asyncio
    async def test_antes_ayer_resuelve_anteayer(self) -> None:
        """SC-G04: 'antes_ayer' callback sets fecha_salida to 2 days ago."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            COT_IDIOMA,
            handle_cot_antes_ayer,
        )

        ctx = ContextoCotizacion()
        update = _make_update_cb("cot_antes_ayer")
        context = _make_context(ctx=ctx)

        mocked_date = datetime.date(2026, 9, 20)
        with patch(
            "garay.infraestructura.telegram.handlers_cotizacion._hoy_bogota",
            return_value=mocked_date,
        ):
            result = await handle_cot_antes_ayer(update, context)

        assert result == COT_IDIOMA
        salida = context.user_data["cotizacion_ctx"].fecha_salida
        assert salida is not None
        assert salida.date() == datetime.date(2026, 9, 18)


class TestOtraFechaState:
    """SC-G05: 'Otra fecha' button transitions to COT_FECHA_TEXTO."""

    @pytest.mark.asyncio
    async def test_otra_fecha_retorna_cot_fecha_texto(self) -> None:
        """SC-G05: handle_cot_otra returns COT_FECHA_TEXTO."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            COT_FECHA_TEXTO,
            handle_cot_otra,
        )

        ctx = ContextoCotizacion()
        update = _make_update_cb("cot_otra")
        context = _make_context(ctx=ctx)
        result = await handle_cot_otra(update, context)
        assert result == COT_FECHA_TEXTO


class TestFechaTexto:
    """SC-G06 / SC-G07: Free-text date input."""

    @pytest.mark.asyncio
    async def test_fecha_valida_avanza_a_idioma(self) -> None:
        """SC-G06: Valid date '15/09/2026' advances to COT_IDIOMA."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            COT_IDIOMA,
            handle_cot_fecha_texto,
        )

        ctx = ContextoCotizacion()
        update = _make_update_text("15/09/2026")
        context = _make_context(ctx=ctx)
        result = await handle_cot_fecha_texto(update, context)
        assert result == COT_IDIOMA
        salida = context.user_data["cotizacion_ctx"].fecha_salida
        assert salida is not None
        assert salida.day == 15
        assert salida.month == 9
        assert salida.year == 2026

    @pytest.mark.asyncio
    async def test_fecha_invalida_re_pregunta(self) -> None:
        """SC-G07: Invalid date text re-asks (returns COT_FECHA_TEXTO)."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            COT_FECHA_TEXTO,
            handle_cot_fecha_texto,
        )

        ctx = ContextoCotizacion()
        update = _make_update_text("not a date")
        context = _make_context(ctx=ctx)
        result = await handle_cot_fecha_texto(update, context)
        assert result == COT_FECHA_TEXTO


# ---------------------------------------------------------------------------
# TASK-5B: /cancelar mid-flow (SC-H01, SC-H02, SC-H03)
# ---------------------------------------------------------------------------


class TestCancelarMidFlow:
    """SC-H01 to SC-H03: /cancelar ends conversation and cleans user_data."""

    @pytest.mark.asyncio
    async def test_cancelar_en_cot_familia_termina_flujo(self) -> None:
        """SC-H01: /cancelar in any state → ConversationHandler.END."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            cmd_cancelar_cotizacion,
        )

        ctx = ContextoCotizacion()
        update = _make_update_command("/cancelar")
        context = _make_context(ctx=ctx)
        result = await cmd_cancelar_cotizacion(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_cancelar_en_cot_confirmar_termina_flujo(self) -> None:
        """SC-H02: /cancelar in COT_CONFIRMAR state → END."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            cmd_cancelar_cotizacion,
        )

        ctx = ContextoCotizacion(
            cliente_nombre="Test",
            adultos=2,
            precio_adulto=Decimal("150000"),
        )
        update = _make_update_command("/cancelar")
        context = _make_context(ctx=ctx)
        result = await cmd_cancelar_cotizacion(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_cancelar_limpia_user_data(self) -> None:
        """SC-H03: cotizacion_ctx removed from user_data on cancellation."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            cmd_cancelar_cotizacion,
        )

        ctx = ContextoCotizacion()
        update = _make_update_command("/cancelar")
        context = _make_context(ctx=ctx)

        assert "cotizacion_ctx" in context.user_data
        await cmd_cancelar_cotizacion(update, context)
        assert "cotizacion_ctx" not in context.user_data


# ---------------------------------------------------------------------------
# TASK-5C: Email delivery (SC-D01 to SC-D04)
# ---------------------------------------------------------------------------


class TestEmailDelivery:
    """SC-D01 to SC-D04: email sent only when cliente_email is present."""

    @pytest.mark.asyncio
    async def test_email_enviado_cuando_hay_email(self) -> None:
        """SC-D01: enviar called once with correct destinatario."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )

        notificador = MagicMock()
        notificador.enviar = MagicMock()

        ctx = ContextoCotizacion(
            cliente_nombre="Juan",
            cliente_email="client@example.com",
            destinos_nombres=["Tour Test"],
            fecha_salida=datetime.datetime(2026, 9, 20),
            adultos=2,
            precio_adulto=Decimal("150000"),
            ninos=0,
            factura_idioma="es",
        )

        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx, notificador_email=notificador)

        await handle_cot_confirmar(update, context)

        notificador.enviar.assert_called_once()
        call_args = notificador.enviar.call_args
        # positional: destinatario, asunto, cuerpo_html
        assert call_args[0][0] == "client@example.com"

    @pytest.mark.asyncio
    async def test_email_no_enviado_cuando_email_none(self) -> None:
        """SC-D02: enviar NOT called when cliente_email is None."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )

        notificador = MagicMock()
        notificador.enviar = MagicMock()

        ctx = ContextoCotizacion(
            cliente_nombre="Juan",
            cliente_email=None,
            destinos_nombres=["Tour Test"],
            fecha_salida=datetime.datetime(2026, 9, 20),
            adultos=2,
            precio_adulto=Decimal("150000"),
            ninos=0,
        )

        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx, notificador_email=notificador)

        await handle_cot_confirmar(update, context)

        notificador.enviar.assert_not_called()

    @pytest.mark.asyncio
    async def test_email_no_enviado_cuando_email_vacio(self) -> None:
        """SC-D03: enviar NOT called when cliente_email is empty string."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )

        notificador = MagicMock()
        notificador.enviar = MagicMock()

        ctx = ContextoCotizacion(
            cliente_nombre="Juan",
            cliente_email="",
            destinos_nombres=["Tour Test"],
            fecha_salida=datetime.datetime(2026, 9, 20),
            adultos=2,
            precio_adulto=Decimal("150000"),
            ninos=0,
        )

        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx, notificador_email=notificador)

        await handle_cot_confirmar(update, context)

        notificador.enviar.assert_not_called()

    @pytest.mark.asyncio
    async def test_asunto_usa_clave_catalogo_es(self) -> None:
        """SC-D04: asunto matches catalog key cotizacion.asunto_email.es for ES."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )
        from garay.mensajes.catalogo import Idioma, obtener_mensaje

        notificador = MagicMock()
        notificador.enviar = MagicMock()

        ctx = ContextoCotizacion(
            cliente_nombre="Juan",
            cliente_email="test@test.com",
            destinos_nombres=["Tour Test"],
            fecha_salida=datetime.datetime(2026, 9, 20),
            adultos=1,
            precio_adulto=Decimal("150000"),
            ninos=0,
            factura_idioma="es",
        )

        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx, notificador_email=notificador)

        await handle_cot_confirmar(update, context)

        notificador.enviar.assert_called_once()
        call_args = notificador.enviar.call_args
        asunto_enviado = call_args[0][1]  # 2nd positional arg = asunto
        expected = obtener_mensaje("cotizacion.asunto_email.es", Idioma.ES)
        assert asunto_enviado == expected


# ---------------------------------------------------------------------------
# TASK-5D: Telegram notification (SC-E01 to SC-E06)
# ---------------------------------------------------------------------------


class TestTelegramNotification:
    """SC-E01 to SC-E06: Telegram notification content and parse mode."""

    async def _confirmar_y_capturar_mensaje(
        self,
        ctx: ContextoCotizacion,
        notificador: MagicMock | None = None,
    ) -> str:
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )

        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx, notificador_email=notificador)

        await handle_cot_confirmar(update, context)

        # Get text of the Telegram notification sent to chat
        context.bot.send_message.assert_called()
        call_kwargs = context.bot.send_message.call_args[1]
        return str(call_kwargs.get("text", ""))

    @pytest.mark.asyncio
    async def test_tour_name_bold_in_notification(self) -> None:
        """SC-E01: Tour name appears in bold."""
        ctx = ContextoCotizacion(
            cliente_nombre="Ana",
            destinos_nombres=["Islas del Rosario"],
            fecha_salida=datetime.datetime(2026, 9, 20),
            adultos=2,
            precio_adulto=Decimal("150000"),
        )
        msg = await self._confirmar_y_capturar_mensaje(ctx)
        assert "Islas del Rosario" in msg
        assert "<b>" in msg

    @pytest.mark.asyncio
    async def test_cliente_nombre_in_notification(self) -> None:
        """SC-E02: Client name appears, bold-marked."""
        ctx = ContextoCotizacion(
            cliente_nombre="Ana Rincón",
            destinos_nombres=["Tour Test"],
            fecha_salida=datetime.datetime(2026, 9, 20),
            adultos=1,
            precio_adulto=Decimal("150000"),
        )
        msg = await self._confirmar_y_capturar_mensaje(ctx)
        assert "Ana Rincón" in msg

    @pytest.mark.asyncio
    async def test_total_price_bold_in_notification(self) -> None:
        """SC-E03: Total price formatted as COP, bold."""
        ctx = ContextoCotizacion(
            cliente_nombre="Test",
            destinos_nombres=["Tour"],
            fecha_salida=datetime.datetime(2026, 9, 20),
            adultos=2,
            precio_adulto=Decimal("150000"),
            ninos=1,
            precio_nino=Decimal("80000"),
        )
        msg = await self._confirmar_y_capturar_mensaje(ctx)
        # 2×150000 + 1×80000 = 380000
        assert "$380.000" in msg

    @pytest.mark.asyncio
    async def test_email_sent_status_shown(self) -> None:
        """SC-E04: When email sent, address appears in notification."""
        notificador = MagicMock()
        notificador.enviar = MagicMock()
        ctx = ContextoCotizacion(
            cliente_nombre="Test",
            cliente_email="x@y.com",
            destinos_nombres=["Tour"],
            fecha_salida=datetime.datetime(2026, 9, 20),
            adultos=1,
            precio_adulto=Decimal("100000"),
        )
        msg = await self._confirmar_y_capturar_mensaje(ctx, notificador=notificador)
        assert "x@y.com" in msg or "Enviado" in msg

    @pytest.mark.asyncio
    async def test_no_email_status_shown(self) -> None:
        """SC-E05: When no email, 'Sin email' indicator in notification."""
        ctx = ContextoCotizacion(
            cliente_nombre="Test",
            cliente_email=None,
            destinos_nombres=["Tour"],
            fecha_salida=datetime.datetime(2026, 9, 20),
            adultos=1,
            precio_adulto=Decimal("100000"),
        )
        msg = await self._confirmar_y_capturar_mensaje(ctx)
        assert "Sin email" in msg or "no se envió" in msg

    @pytest.mark.asyncio
    async def test_parse_mode_html(self) -> None:
        """SC-E06: Telegram message uses parse_mode='HTML'."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )

        ctx = ContextoCotizacion(
            cliente_nombre="Test",
            destinos_nombres=["Tour"],
            fecha_salida=datetime.datetime(2026, 9, 20),
            adultos=1,
            precio_adulto=Decimal("100000"),
        )
        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx)
        await handle_cot_confirmar(update, context)

        context.bot.send_message.assert_called()
        call_kwargs = context.bot.send_message.call_args[1]
        assert call_kwargs.get("parse_mode") == "HTML"


# ---------------------------------------------------------------------------
# TASK-5F: Happy path integration (SC-I01 to SC-I05)
# ---------------------------------------------------------------------------


class TestHappyPathIntegration:
    """SC-I01 to SC-I05: Full flow scenarios (mocked bot_data)."""

    @pytest.mark.asyncio
    async def test_happy_path_email_sent(self) -> None:
        """SC-I01: Full flow — generar called, email sent, Telegram notif sent."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )

        notificador = MagicMock()
        notificador.enviar = MagicMock()

        ctx = ContextoCotizacion(
            cliente_nombre="Juan Test",
            cliente_email="j@t.com",
            destinos_nombres=["Tour Test"],
            fecha_salida=datetime.datetime(2026, 9, 19),
            adultos=2,
            precio_adulto=Decimal("150000"),
            ninos=1,
            precio_nino=Decimal("80000"),
            factura_idioma="es",
        )

        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx, notificador_email=notificador)

        result = await handle_cot_confirmar(update, context)

        assert result == ConversationHandler.END
        notificador.enviar.assert_called_once()
        context.bot.send_message.assert_called_once()
        msg_text = context.bot.send_message.call_args[1].get("text", "")
        assert "$380.000" in msg_text
        assert "Juan Test" in msg_text

    @pytest.mark.asyncio
    async def test_skip_email_path(self) -> None:
        """SC-I02: Skip email → enviar NOT called, Telegram sent with no-email indicator."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )

        notificador = MagicMock()
        notificador.enviar = MagicMock()

        ctx = ContextoCotizacion(
            cliente_nombre="Juan Test",
            cliente_email=None,
            destinos_nombres=["Tour Test"],
            fecha_salida=datetime.datetime(2026, 9, 19),
            adultos=2,
            precio_adulto=Decimal("150000"),
            ninos=0,
        )

        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx, notificador_email=notificador)

        await handle_cot_confirmar(update, context)

        notificador.enviar.assert_not_called()
        context.bot.send_message.assert_called_once()
        msg_text = context.bot.send_message.call_args[1].get("text", "")
        assert "Sin email" in msg_text or "no se envió" in msg_text

    @pytest.mark.asyncio
    async def test_skip_ninos_path(self) -> None:
        """SC-I03: Skip ninos → ninos=0, valor_total = 2×150000 = 300000."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )

        ctx = ContextoCotizacion(
            cliente_nombre="Juan",
            destinos_nombres=["Tour Test"],
            fecha_salida=datetime.datetime(2026, 9, 19),
            adultos=2,
            precio_adulto=Decimal("150000"),
            ninos=0,
        )
        assert ctx.valor_total == Decimal("300000")

        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx)
        result = await handle_cot_confirmar(update, context)
        assert result == ConversationHandler.END
        msg_text = context.bot.send_message.call_args[1].get("text", "")
        assert "$300.000" in msg_text

    @pytest.mark.asyncio
    async def test_skip_email_and_ninos(self) -> None:
        """SC-I04: Skip both → no enviar, valor_total = 1×150000 = 150000."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )

        notificador = MagicMock()
        notificador.enviar = MagicMock()

        ctx = ContextoCotizacion(
            cliente_nombre="Test",
            cliente_email=None,
            destinos_nombres=["Tour"],
            fecha_salida=datetime.datetime(2026, 9, 19),
            adultos=1,
            precio_adulto=Decimal("150000"),
            ninos=0,
        )

        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx, notificador_email=notificador)

        await handle_cot_confirmar(update, context)

        notificador.enviar.assert_not_called()
        msg_text = context.bot.send_message.call_args[1].get("text", "")
        assert "$150.000" in msg_text

    @pytest.mark.asyncio
    async def test_en_language_html_title(self) -> None:
        """SC-I05: EN idioma → generated HTML has 'SERVICE QUOTE'."""
        from garay.infraestructura.telegram.handlers_cotizacion import (
            handle_cot_confirmar,
        )
        from garay.aplicacion.cotizacion.servicio import GenerarCotizacionService

        captured_html: list[str] = []
        original_generar = GenerarCotizacionService.generar

        def _spy_generar(
            self: GenerarCotizacionService,
            ctx: ContextoCotizacion,
        ) -> str:
            result = original_generar(self, ctx)
            captured_html.append(result)
            return result

        ctx = ContextoCotizacion(
            cliente_nombre="Test",
            destinos_nombres=["Tour"],
            fecha_salida=datetime.datetime(2026, 9, 19),
            adultos=1,
            precio_adulto=Decimal("100000"),
            factura_idioma="en",
        )

        update = _make_update_cb("cot_confirmar")
        context = _make_context(ctx=ctx)

        with patch.object(GenerarCotizacionService, "generar", _spy_generar):
            await handle_cot_confirmar(update, context)

        assert captured_html, "generar was not called"
        assert "SERVICE QUOTE" in captured_html[0]
        assert "COTIZACIÓN DE SERVICIO" not in captured_html[0]
