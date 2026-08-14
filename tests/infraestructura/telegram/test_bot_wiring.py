"""Tests that verify bot.py ConversationHandler state wiring for fl: callbacks.

Phase 8 (WU-2): PARTICIPANTE_OTRO, EDITAR_VENDEDOR, EDITAR_CERRADOR states must
each contain at least one CallbackQueryHandler with pattern '^fl:' so picker
button clicks reach the FSM.
"""

from __future__ import annotations

from decimal import Decimal
from re import Pattern
from unittest.mock import MagicMock, patch

from telegram.ext import CallbackQueryHandler, ConversationHandler

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.infraestructura.telegram.bot import crear_aplicacion
from garay.infraestructura.telegram.estados import ESTADO_PTB


def _fsm() -> FSMTiquetera:
    servicios: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
        (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ", []),
    ]
    return FSMTiquetera(servicios=servicios, puntos_venta=["Marie Real"])


def _build_handler() -> ConversationHandler:  # type: ignore[type-arg]
    """Build the ConversationHandler from crear_aplicacion without running the event loop."""
    token = "fake:token"
    with patch("garay.infraestructura.telegram.bot.obtener_settings") as mock_settings:
        settings = MagicMock()
        settings.propietario_telegram_ids = ""
        settings.dev_telegram_ids = ""
        mock_settings.return_value = settings
        app = crear_aplicacion(token)

    # The first handler added is the main ConversationHandler for tiquetera.
    return app.handlers[0][0]  # type: ignore[return-value]


def _fl_states_with_callback(conv: ConversationHandler) -> dict[int, bool]:  # type: ignore[type-arg]
    """Return mapping of state_int → True if any CallbackQueryHandler matches '^fl:'."""
    result: dict[int, bool] = {}
    for state_int, handlers in conv.states.items():
        has_fl = any(
            isinstance(h, CallbackQueryHandler)
            and isinstance(h.pattern, Pattern)
            and "fl:" in h.pattern.pattern
            for h in handlers
        )
        result[state_int] = has_fl  # type: ignore[index]
    return result


class TestBotWiringFlCallbacks:
    """Phase 8 — PARTICIPANTE_OTRO, EDITAR_VENDEDOR, EDITAR_CERRADOR have ^fl: callbacks."""

    def test_participante_otro_has_fl_callback(self) -> None:
        """PARTICIPANTE_OTRO state list must contain a CallbackQueryHandler(pattern='^fl:')."""
        conv = _build_handler()
        state_int = ESTADO_PTB[EstadoFSM.PARTICIPANTE_OTRO]
        handlers = conv.states.get(state_int, [])
        fl_handlers = [
            h for h in handlers
            if isinstance(h, CallbackQueryHandler)
            and isinstance(h.pattern, Pattern)
            and "fl:" in h.pattern.pattern
        ]
        assert len(fl_handlers) >= 1, (
            f"PARTICIPANTE_OTRO (state {state_int}) has no CallbackQueryHandler"
            f" with 'fl:' pattern. Handlers found: {handlers}"
        )

    def test_editar_vendedor_has_fl_callback(self) -> None:
        """EDITAR_VENDEDOR state list must contain a CallbackQueryHandler(pattern='^fl:')."""
        conv = _build_handler()
        state_int = ESTADO_PTB[EstadoFSM.EDITAR_VENDEDOR]
        handlers = conv.states.get(state_int, [])
        fl_handlers = [
            h for h in handlers
            if isinstance(h, CallbackQueryHandler)
            and isinstance(h.pattern, Pattern)
            and "fl:" in h.pattern.pattern
        ]
        assert len(fl_handlers) >= 1, (
            f"EDITAR_VENDEDOR (state {state_int}) has no CallbackQueryHandler"
            f" with 'fl:' pattern. Handlers found: {handlers}"
        )

    def test_editar_cerrador_has_fl_callback(self) -> None:
        """EDITAR_CERRADOR state list must contain a CallbackQueryHandler(pattern='^fl:')."""
        conv = _build_handler()
        state_int = ESTADO_PTB[EstadoFSM.EDITAR_CERRADOR]
        handlers = conv.states.get(state_int, [])
        fl_handlers = [
            h for h in handlers
            if isinstance(h, CallbackQueryHandler)
            and isinstance(h.pattern, Pattern)
            and "fl:" in h.pattern.pattern
        ]
        assert len(fl_handlers) >= 1, (
            f"EDITAR_CERRADOR (state {state_int}) has no CallbackQueryHandler"
            f" with 'fl:' pattern. Handlers found: {handlers}"
        )


class TestBotWiringHorarioSalida:
    """Phase 10 — HORARIO_SALIDA state is registered in the ConversationHandler.

    Spec: Domain 1 / Scenario 'bot.py states dict contains HORARIO_SALIDA'.
    Rules:
      - ESTADO_PTB[EstadoFSM.HORARIO_SALIDA] == 31
      - A CallbackQueryHandler with pattern '^hor:' is registered for that state
      - A MessageHandler is also registered (defensive re-render)
    """

    def test_horario_salida_ptb_value_is_31(self) -> None:
        """ESTADO_PTB[EstadoFSM.HORARIO_SALIDA] must equal 31."""
        assert ESTADO_PTB[EstadoFSM.HORARIO_SALIDA] == 31

    def test_horario_salida_state_registered_in_conv_handler(self) -> None:
        """HORARIO_SALIDA state (31) must appear in ConversationHandler states."""
        conv = _build_handler()
        state_int = ESTADO_PTB[EstadoFSM.HORARIO_SALIDA]
        assert state_int in conv.states, (
            f"HORARIO_SALIDA (state {state_int}) is not registered in ConversationHandler. "
            f"Registered states: {list(conv.states.keys())}"
        )

    def test_horario_salida_has_hor_callback(self) -> None:
        """HORARIO_SALIDA must have a CallbackQueryHandler matching '^hor:'."""
        conv = _build_handler()
        state_int = ESTADO_PTB[EstadoFSM.HORARIO_SALIDA]
        handlers = conv.states.get(state_int, [])
        hor_handlers = [
            h for h in handlers
            if isinstance(h, CallbackQueryHandler)
            and isinstance(h.pattern, Pattern)
            and "hor:" in h.pattern.pattern
        ]
        assert len(hor_handlers) >= 1, (
            f"HORARIO_SALIDA (state {state_int}) has no CallbackQueryHandler"
            f" with 'hor:' pattern. Handlers found: {handlers}"
        )
