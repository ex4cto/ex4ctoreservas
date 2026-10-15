"""Port definition for text message notification."""

from __future__ import annotations

from abc import ABC, abstractmethod


class NotificadorTextoPort(ABC):
    """Port: send a plain-text or HTML Telegram message to a chat."""

    @abstractmethod
    async def enviar(self, chat_id: int, texto: str) -> None:
        """Send text to the given chat_id."""
        ...
