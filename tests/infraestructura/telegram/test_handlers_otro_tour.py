"""Tests for Slice 2 — otro-tour handler and CONFIRMACION registration hook."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera, SalidaFSM
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta
from garay.infraestructura.telegram.estados import ESTADO_PTB
from garay.mensajes.catalogo import obtener_mensaje

# ---------------------------------------------------------------------------
# Helpers — mirrors pattern from test_handlers_ventas.py / test_handlers_fecha_por_tour.py
# ---------------------------------------------------------------------------

_SERVICIOS: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARU"),
]
_PUNTOS: list[str] = ["Marie Real"]
_SRV_UUID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
_FL_UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _make_fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=_SERVICIOS, puntos_venta=_PUNTOS)


def _make_ctx_listo() -> ContextoVenta:
    """Context that passes all guards in _contexto_a_comando."""
    return ContextoVenta(
        tipo_cliente=TipoCliente.EXTERNO,
        punto_de_venta_nombre="Marie Real",
        canal_origen="WhatsApp",
        cliente_nombre="Juan Perez",
        cliente_telefono="3001234567",
        cliente_email="juan@example.com",
        cliente_identificacion="123456789",
        cliente_tipo_identificacion="CC",
        sin_hotel=True,
        destinos_numeros=[1],
        fecha_salida=__import__("datetime").datetime(2026, 9, 15, 8, 0),
        adultos=2,
        ninos=0,
        valor=Decimal("300000"),
        abono=Decimal("0"),
        neto=Decimal("200000"),
        rol_registrante="ambos",
    )


def _make_update_cb(data: str) -> MagicMock:
    """Update with callback_query."""
    update = MagicMock()
    update.message = None
    update.effective_chat = MagicMock()
    update.effective_chat.id = 12345
    update.effective_user = MagicMock()
    update.effective_user.id = 99999
    update.effective_message = AsyncMock()
    cq = AsyncMock()
    cq.data = data
    cq.answer = AsyncMock()
    cq.edit_message_text = AsyncMock()
    update.callback_query = cq
    return update


def _make_update_text(text: str) -> MagicMock:
    """Update with text message."""
    update = MagicMock()
    update.callback_query = None
    update.effective_chat = MagicMock()
    update.effective_chat.id = 12345
    update.effective_user = MagicMock()
    update.effective_user.id = 99999
    update.effective_message = AsyncMock()
    msg = AsyncMock()
    msg.text = text
    msg.reply_text = AsyncMock()
    update.message = msg
    return update


def _make_context(
    *,
    fsm: FSMTiquetera | None = None,
    ctx: ContextoVenta | None = None,
    bot_data_extra: dict | None = None,  # type: ignore[type-arg]
    user_data_extra: dict | None = None,  # type: ignore[type-arg]
) -> MagicMock:
    """Build a PTB-like context mock."""
    context = MagicMock()

    # bot_data
    fsm_inst = fsm or _make_fsm()
    fl_repo = MagicMock()
    fl_repo.buscar_por_telegram_id.return_value = _make_freelancer()
    srv_repo = MagicMock()
    srv_mock = MagicMock()
    srv_mock.numero = 1
    srv_mock.id = _SRV_UUID
    srv_repo.listar.return_value = [srv_mock]
    cliente_repo = MagicMock()
    cliente_repo.buscar_por_nombre_y_telefono.return_value = None

    bot_data: dict[str, object] = {
        "fsm": fsm_inst,
        "freelancer_repo": fl_repo,
        "servicio_repo": srv_repo,
        "cliente_repo": cliente_repo,
    }
    if bot_data_extra:
        bot_data.update(bot_data_extra)
    context.bot_data = bot_data

    # user_data
    user_data: dict[str, object] = {}
    if ctx:
        user_data["contexto"] = ctx
    if user_data_extra:
        user_data.update(user_data_extra)
    context.user_data = user_data

    # bot
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()

    return context


def _make_freelancer() -> MagicMock:
    fl = MagicMock()
    fl.id = _FL_UUID
    fl.nombre = "Maria Lopez"
    return fl


def _make_registro_service() -> MagicMock:
    """A registrar_venta_service that succeeds."""
    svc = MagicMock()
    resultado = MagicMock()
    desglose = MagicMock()
    desglose.vendedor = MagicMock()
    desglose.vendedor.monto = Decimal("50000")
    desglose.cerrador = MagicMock()
    desglose.cerrador.monto = Decimal("50000")
    desglose.vendedor.__add__ = lambda self, other: other  # type: ignore[assignment]
    resultado.desglose = desglose
    svc.ejecutar.return_value = resultado
    return svc


# ---------------------------------------------------------------------------
# Task 6a: CONFIRMACION handler → returns OTRO_TOUR on success
# ---------------------------------------------------------------------------


class TestConfirmacionOtroTourHook:
    """After successful registration, handler must return ESTADO_PTB[OTRO_TOUR]."""

    @pytest.mark.asyncio
    async def test_successful_registration_returns_otro_tour_state(self) -> None:
        from garay.infraestructura.telegram.handlers import handle_confirmacion

        ctx_venta = _make_ctx_listo()
        # A listo=True SalidaFSM is returned when FSM processes "✅ Confirmar"
        fsm = _make_fsm()
        svc = _make_registro_service()

        update = _make_update_cb("✅ Confirmar")
        context = _make_context(
            fsm=fsm, ctx=ctx_venta, bot_data_extra={"registrar_venta_service": svc}
        )

        # Patch FSMTiquetera.procesar_foto to return listo=True
        salida_listo = SalidaFSM(
            nuevo_estado=EstadoFSM.TERMINADO,
            mensaje="ok",
            listo=True,
            contexto=ctx_venta,
        )
        with patch.object(fsm, "procesar_foto", return_value=salida_listo):
            result = await handle_confirmacion(update, context)

        assert result == ESTADO_PTB[EstadoFSM.OTRO_TOUR]

    @pytest.mark.asyncio
    async def test_successful_registration_increments_counter_to_1(self) -> None:
        from garay.infraestructura.telegram.handlers import handle_confirmacion

        ctx_venta = _make_ctx_listo()
        fsm = _make_fsm()
        svc = _make_registro_service()

        update = _make_update_cb("✅ Confirmar")
        context = _make_context(
            fsm=fsm, ctx=ctx_venta, bot_data_extra={"registrar_venta_service": svc}
        )

        salida_listo = SalidaFSM(
            nuevo_estado=EstadoFSM.TERMINADO,
            mensaje="ok",
            listo=True,
            contexto=ctx_venta,
        )
        with patch.object(fsm, "procesar_foto", return_value=salida_listo):
            await handle_confirmacion(update, context)

        assert context.user_data.get("reservas_registradas") == 1

    @pytest.mark.asyncio
    async def test_second_successful_registration_increments_counter_to_2(self) -> None:
        from garay.infraestructura.telegram.handlers import handle_confirmacion

        ctx_venta = _make_ctx_listo()
        fsm = _make_fsm()
        svc = _make_registro_service()

        update = _make_update_cb("✅ Confirmar")
        context = _make_context(
            fsm=fsm,
            ctx=ctx_venta,
            bot_data_extra={"registrar_venta_service": svc},
            user_data_extra={"reservas_registradas": 1},
        )

        salida_listo = SalidaFSM(
            nuevo_estado=EstadoFSM.TERMINADO,
            mensaje="ok",
            listo=True,
            contexto=ctx_venta,
        )
        with patch.object(fsm, "procesar_foto", return_value=salida_listo):
            await handle_confirmacion(update, context)

        assert context.user_data.get("reservas_registradas") == 2

    @pytest.mark.asyncio
    async def test_registration_failure_returns_end(self) -> None:
        """Regression: exception during registration still returns ConversationHandler.END."""
        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.handlers import handle_confirmacion

        ctx_venta = _make_ctx_listo()
        fsm = _make_fsm()

        # Service raises
        svc = MagicMock()
        svc.ejecutar.side_effect = RuntimeError("DB error")

        update = _make_update_cb("✅ Confirmar")
        context = _make_context(
            fsm=fsm, ctx=ctx_venta, bot_data_extra={"registrar_venta_service": svc}
        )

        salida_listo = SalidaFSM(
            nuevo_estado=EstadoFSM.TERMINADO,
            mensaje="ok",
            listo=True,
            contexto=ctx_venta,
        )
        with patch.object(fsm, "procesar_foto", return_value=salida_listo):
            result = await handle_confirmacion(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_otro_tour_prompt_sent_as_new_message_not_edit(self) -> None:
        """OTRO_TOUR prompt must be a NEW send_message, not edit_message_text (Fix 2)."""
        from garay.infraestructura.telegram.handlers import handle_confirmacion

        ctx_venta = _make_ctx_listo()
        fsm = _make_fsm()
        svc = _make_registro_service()

        update = _make_update_cb("✅ Confirmar")
        context = _make_context(
            fsm=fsm, ctx=ctx_venta, bot_data_extra={"registrar_venta_service": svc}
        )

        salida_listo = SalidaFSM(
            nuevo_estado=EstadoFSM.TERMINADO,
            mensaje="ok",
            listo=True,
            contexto=ctx_venta,
        )
        with patch.object(fsm, "procesar_foto", return_value=salida_listo):
            await handle_confirmacion(update, context)

        # The OTRO_TOUR prompt must arrive via send_message (new message below success msg)
        send_calls = context.bot.send_message.call_args_list
        pregunta = obtener_mensaje("pregunta_otro_tour").format(cliente="Juan Perez")
        found = any(pregunta in str(call) for call in send_calls)
        assert found, f"pregunta_otro_tour not found in send_message calls: {send_calls}"
        # edit_message_text must NOT have been used for the OTRO_TOUR prompt
        edit_calls = update.callback_query.edit_message_text.call_args_list
        edit_with_prompt = any(pregunta in str(call) for call in edit_calls)
        assert not edit_with_prompt, (
            f"pregunta_otro_tour was incorrectly sent via edit_message_text: {edit_calls}"
        )


# ---------------------------------------------------------------------------
# Task 6b: handle_otro_tour
# ---------------------------------------------------------------------------


class TestHandleOtroTour:
    """handle_otro_tour routes based on callback data."""

    @pytest.mark.asyncio
    async def test_boton_otro_tour_calls_iniciar_otro_tour(self) -> None:
        """Pressing the otro-tour button calls iniciar_otro_tour and routes to FAMILIA."""
        from garay.infraestructura.telegram.handlers import handle_otro_tour

        fsm = _make_fsm()
        ctx_venta = _make_ctx_listo()
        boton = obtener_mensaje("boton_otro_tour")

        update = _make_update_cb(boton)
        context = _make_context(fsm=fsm, ctx=ctx_venta)

        result = await handle_otro_tour(update, context)

        assert result == ESTADO_PTB[EstadoFSM.FAMILIA]

    @pytest.mark.asyncio
    async def test_boton_terminar_returns_end(self) -> None:
        """Pressing '🏁 Terminar' ends the conversation."""
        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.handlers import handle_otro_tour

        fsm = _make_fsm()
        ctx_venta = _make_ctx_listo()
        boton = obtener_mensaje("boton_terminar")

        update = _make_update_cb(boton)
        context = _make_context(
            fsm=fsm,
            ctx=ctx_venta,
            user_data_extra={"reservas_registradas": 2},
        )

        result = await handle_otro_tour(update, context)

        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_boton_terminar_resets_counter(self) -> None:
        """Pressing '🏁 Terminar' resets reservas_registradas to 0."""
        from garay.infraestructura.telegram.handlers import handle_otro_tour

        fsm = _make_fsm()
        ctx_venta = _make_ctx_listo()
        boton = obtener_mensaje("boton_terminar")

        update = _make_update_cb(boton)
        context = _make_context(
            fsm=fsm,
            ctx=ctx_venta,
            user_data_extra={"reservas_registradas": 3},
        )

        await handle_otro_tour(update, context)

        assert context.user_data.get("reservas_registradas") == 0

    @pytest.mark.asyncio
    async def test_boton_terminar_sends_resumen(self) -> None:
        """Pressing '🏁 Terminar' sends a resumen message with the counter."""
        from garay.infraestructura.telegram.handlers import handle_otro_tour

        fsm = _make_fsm()
        ctx_venta = _make_ctx_listo()
        boton = obtener_mensaje("boton_terminar")

        update = _make_update_cb(boton)
        context = _make_context(
            fsm=fsm,
            ctx=ctx_venta,
            user_data_extra={"reservas_registradas": 2},
        )

        await handle_otro_tour(update, context)

        # Either edit_message_text or reply_text must have been called with "2" in text
        all_calls = (
            list(update.callback_query.edit_message_text.call_args_list)
            + list(update.effective_message.reply_text.call_args_list)
        )
        found = any(
            "2" in str(call) for call in all_calls
        )
        assert found, f"Counter '2' not found in send calls: {all_calls}"

    @pytest.mark.asyncio
    async def test_unknown_input_stays_in_otro_tour(self) -> None:
        """Any other input re-sends the prompt and stays in OTRO_TOUR."""
        from garay.infraestructura.telegram.handlers import handle_otro_tour

        fsm = _make_fsm()
        ctx_venta = _make_ctx_listo()

        update = _make_update_cb("gibberish")
        context = _make_context(fsm=fsm, ctx=ctx_venta)

        result = await handle_otro_tour(update, context)

        assert result == ESTADO_PTB[EstadoFSM.OTRO_TOUR]


# ---------------------------------------------------------------------------
# Fix 1: handle_iniciar_venta resets reservas_registradas counter
# ---------------------------------------------------------------------------


class TestIniciarVentaResetsCounter:
    """handle_iniciar_venta must reset reservas_registradas to 0 on every new sale."""

    @pytest.mark.asyncio
    async def test_resets_stale_counter_to_zero(self) -> None:
        """Counter left over from a previous session must be zeroed at sale start."""
        from unittest.mock import patch

        from garay.infraestructura.telegram.handlers import handle_iniciar_venta

        fsm = _make_fsm()
        update = _make_update_text("/nueva_venta")
        context = _make_context(fsm=fsm, user_data_extra={"reservas_registradas": 5})

        # Patch FSM.iniciar to avoid real state transitions
        salida_inicio = __import__(
            "garay.aplicacion.tiquetera.fsm", fromlist=["SalidaFSM"]
        ).SalidaFSM(
            nuevo_estado=__import__(
                "garay.aplicacion.tiquetera.fsm", fromlist=["EstadoFSM"]
            ).EstadoFSM.METODO_INPUT,
            mensaje="¿Cómo registrás?",
            contexto=None,
        )
        with patch.object(fsm, "iniciar", return_value=salida_inicio):
            await handle_iniciar_venta(update, context)

        assert context.user_data.get("reservas_registradas") == 0
