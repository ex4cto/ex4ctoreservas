"""Every ConversationHandler must let /start break out of an active flow (gap 5).

Before this fix the only fallback was /cancelar, so mid-flow /start (the menu
command) did nothing and the bot felt stuck. /start is now a universal escape,
and the sales flow allows re-entry so /nueva_venta restarts it cleanly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from telegram.ext import Application, CommandHandler, ConversationHandler

from garay.infraestructura.telegram.bot import crear_aplicacion


def _build_app() -> Application:  # type: ignore[type-arg]
    with patch("garay.infraestructura.telegram.bot.obtener_settings") as mock_settings:
        settings = MagicMock()
        settings.propietario_telegram_ids = ""
        settings.dev_telegram_ids = ""
        mock_settings.return_value = settings
        return crear_aplicacion("fake:token")


def _conversation_handlers(app: Application) -> list[ConversationHandler]:  # type: ignore[type-arg]
    return [
        h
        for grupo in app.handlers.values()
        for h in grupo
        if isinstance(h, ConversationHandler)
    ]


def _tiene_start_en_fallbacks(conv: ConversationHandler) -> bool:  # type: ignore[type-arg]
    return any(
        isinstance(h, CommandHandler) and "start" in h.commands for h in conv.fallbacks
    )


class TestStartEscapaCualquierFlujo:
    def test_hay_varios_conversation_handlers(self) -> None:
        assert len(_conversation_handlers(_build_app())) >= 5

    def test_todos_los_flujos_tienen_start_como_fallback(self) -> None:
        convs = _conversation_handlers(_build_app())
        faltantes = [c for c in convs if not _tiene_start_en_fallbacks(c)]
        assert not faltantes, (
            f"{len(faltantes)} ConversationHandlers sin /start en fallbacks"
        )

    def test_flujo_ventas_permite_reentry(self) -> None:
        app = _build_app()
        # The sales ConversationHandler is the first handler added (group 0).
        conv = app.handlers[0][0]
        assert isinstance(conv, ConversationHandler)
        assert conv.allow_reentry is True
