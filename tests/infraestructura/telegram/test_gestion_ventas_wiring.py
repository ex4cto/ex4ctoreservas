"""Tests that verify Phase 2.10 DI wiring for editar-neto / editar-valor-venta.

Phase 2.10.1 RED: bot_data contains the new service keys after container setup;
bot.py ConversationHandler has GV_EDIT_NETO and GV_EDIT_VALOR_VENTA states.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from telegram.ext import ConversationHandler, MessageHandler

from garay.aplicacion.tiquetera.fsm import FSMTiquetera
from garay.infraestructura.telegram.bot import crear_aplicacion


def _build_gv_handler() -> ConversationHandler:  # type: ignore[type-arg]
    """Build the gestionar_ventas ConversationHandler from crear_aplicacion."""
    token = "fake:token"
    with patch("garay.infraestructura.telegram.bot.obtener_settings") as mock_settings:
        settings = MagicMock()
        settings.propietario_telegram_ids = ""
        settings.dev_telegram_ids = ""
        mock_settings.return_value = settings
        app = crear_aplicacion(token)

    # Find the gestionar_ventas ConversationHandler by looking for GV_EDIT_NETO state.
    from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_NETO

    for handler_group in app.handlers.values():
        for handler in handler_group:
            if isinstance(handler, ConversationHandler):
                if GV_EDIT_NETO in handler.states:
                    return handler
    raise AssertionError("gestionar_ventas ConversationHandler not found")


class TestGestionVentasWiring:
    def test_gv_edit_neto_state_registered(self) -> None:
        """GV_EDIT_NETO (232) must be a registered state in the gv ConversationHandler."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_NETO

        conv = _build_gv_handler()
        assert GV_EDIT_NETO in conv.states, (
            f"GV_EDIT_NETO={GV_EDIT_NETO} not found in states: {list(conv.states.keys())}"
        )

    def test_gv_edit_valor_venta_state_registered(self) -> None:
        """GV_EDIT_VALOR_VENTA (233) must be a registered state in the gv ConversationHandler."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_VALOR_VENTA

        conv = _build_gv_handler()
        assert GV_EDIT_VALOR_VENTA in conv.states, (
            f"GV_EDIT_VALOR_VENTA={GV_EDIT_VALOR_VENTA} not found in states: {list(conv.states.keys())}"
        )

    def test_gv_edit_neto_state_has_message_handler(self) -> None:
        """GV_EDIT_NETO state must contain a MessageHandler for text input."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_NETO

        conv = _build_gv_handler()
        handlers = conv.states[GV_EDIT_NETO]
        assert any(isinstance(h, MessageHandler) for h in handlers), (
            "GV_EDIT_NETO state has no MessageHandler"
        )

    def test_gv_edit_valor_venta_state_has_message_handler(self) -> None:
        """GV_EDIT_VALOR_VENTA state must contain a MessageHandler for text input."""
        from garay.infraestructura.telegram.handlers_gestion_ventas import GV_EDIT_VALOR_VENTA

        conv = _build_gv_handler()
        handlers = conv.states[GV_EDIT_VALOR_VENTA]
        assert any(isinstance(h, MessageHandler) for h in handlers), (
            "GV_EDIT_VALOR_VENTA state has no MessageHandler"
        )
