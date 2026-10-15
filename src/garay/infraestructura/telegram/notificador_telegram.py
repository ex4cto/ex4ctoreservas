"""Telegram implementation of NotificadorTextoPort."""

from __future__ import annotations

from telegram import Bot

from garay.dominio.puertos.notificador_texto import NotificadorTextoPort


class NotificadorTelegramTexto(NotificadorTextoPort):
    """Sends HTML text messages via the Telegram Bot API."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def enviar(self, chat_id: int, texto: str) -> None:
        """Send an HTML-formatted message to the given chat_id."""
        await self._bot.send_message(chat_id=chat_id, text=texto, parse_mode="HTML")
