"""Error types for the Telegram notifier adapter."""


class NotificadorNoDisponible(Exception):
    """Telegram API is unreachable (network error)."""


class NotificadorError(Exception):
    """Telegram API returned a non-2xx response."""
