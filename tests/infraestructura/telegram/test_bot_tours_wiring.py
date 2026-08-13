"""Smoke tests that verify bot.py registers the tour conversation handlers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from telegram.ext import Application, ConversationHandler

from garay.infraestructura.telegram.bot import crear_aplicacion


def _build_app() -> Application:  # type: ignore[type-arg]
    token = "fake:token"
    with patch("garay.infraestructura.telegram.bot.obtener_settings") as mock_settings:
        settings = MagicMock()
        settings.propietario_telegram_ids = ""
        settings.dev_telegram_ids = ""
        mock_settings.return_value = settings
        return crear_aplicacion(token)


class TestBotToursWiring:
    def test_editar_tour_conv_handler_registered(self) -> None:
        """editar_tour_conv_handler must be registered in the application."""

        app = _build_app()
        # Collect all entry-point handlers across all groups
        entry_commands: list[str] = []
        for _group, handlers in app.handlers.items():
            for h in handlers:
                if isinstance(h, ConversationHandler):
                    for ep in h.entry_points:
                        if hasattr(ep, "commands"):
                            entry_commands.extend(ep.commands)
        assert "editar_tour" in entry_commands, (
            "editar_tour_conv_handler not registered in bot.py"
        )

    def test_eliminar_tour_conv_handler_registered(self) -> None:
        """eliminar_tour_conv_handler must be registered in the application."""
        app = _build_app()
        entry_commands: list[str] = []
        for _group, handlers in app.handlers.items():
            for h in handlers:
                if isinstance(h, ConversationHandler):
                    for ep in h.entry_points:
                        if hasattr(ep, "commands"):
                            entry_commands.extend(ep.commands)
        assert "eliminar_tour" in entry_commands, (
            "eliminar_tour_conv_handler not registered in bot.py"
        )
