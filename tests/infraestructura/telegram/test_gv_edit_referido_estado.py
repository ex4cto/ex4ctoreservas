"""Tests that GV_EDIT_REFERIDO=241 is registered in the gestionar_ventas ConversationHandler.

Task 5.3: assert state 241 is registered and maps to the correct handlers.
"""

from __future__ import annotations

from re import Pattern
from unittest.mock import MagicMock, patch

from telegram.ext import CallbackQueryHandler, ConversationHandler, MessageHandler

from garay.infraestructura.telegram.handlers_gestion_ventas import (
    GV_EDIT_REFERIDO,
    handle_gv_capturar_referido,
    handle_gv_referido_sin,
)


def _build_gestionar_ventas_handler() -> ConversationHandler:  # type: ignore[type-arg]
    """Build the gestionar_ventas ConversationHandler from crear_aplicacion."""
    from garay.infraestructura.telegram.bot import crear_aplicacion

    token = "fake:token"
    with patch("garay.infraestructura.telegram.bot.obtener_settings") as mock_settings:
        settings = MagicMock()
        settings.propietario_telegram_ids = ""
        settings.dev_telegram_ids = ""
        mock_settings.return_value = settings
        app = crear_aplicacion(token)

    # gestionar_ventas_conv_handler is registered in group 7
    for handler in app.handlers.get(7, []):
        if isinstance(handler, ConversationHandler):
            return handler  # type: ignore[return-value]

    raise AssertionError("gestionar_ventas ConversationHandler not found in group 7")


class TestGvEditReferidoEstado:
    """GV_EDIT_REFERIDO (241) must be registered in the gestionar_ventas handler."""

    def test_gv_edit_referido_constant_value(self) -> None:
        """GV_EDIT_REFERIDO must equal 241."""
        assert GV_EDIT_REFERIDO == 241

    def test_gv_edit_referido_state_registered(self) -> None:
        """State 241 must appear in gestionar_ventas ConversationHandler states."""
        conv = _build_gestionar_ventas_handler()
        assert GV_EDIT_REFERIDO in conv.states, (
            f"GV_EDIT_REFERIDO (241) not found in gestionar_ventas states. "
            f"Registered states: {sorted(conv.states.keys())}"
        )

    def test_gv_edit_referido_has_message_handler(self) -> None:
        """State 241 must contain a MessageHandler (text capture for alias)."""
        conv = _build_gestionar_ventas_handler()
        handlers = conv.states.get(GV_EDIT_REFERIDO, [])
        msg_handlers = [h for h in handlers if isinstance(h, MessageHandler)]
        assert len(msg_handlers) >= 1, (
            f"GV_EDIT_REFERIDO (241) has no MessageHandler. Handlers: {handlers}"
        )

    def test_gv_edit_referido_has_callback_for_sin(self) -> None:
        """State 241 must contain a CallbackQueryHandler matching 'gv_referido_sin'."""
        conv = _build_gestionar_ventas_handler()
        handlers = conv.states.get(GV_EDIT_REFERIDO, [])
        sin_handlers = [
            h for h in handlers
            if isinstance(h, CallbackQueryHandler)
            and isinstance(h.pattern, Pattern)
            and "gv_referido_sin" in h.pattern.pattern
        ]
        assert len(sin_handlers) >= 1, (
            f"GV_EDIT_REFERIDO (241) has no CallbackQueryHandler for 'gv_referido_sin'. "
            f"Handlers: {handlers}"
        )
