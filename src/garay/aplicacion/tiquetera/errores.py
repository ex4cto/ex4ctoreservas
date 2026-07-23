"""Application-layer errors for the tiquetera service."""

from __future__ import annotations


class ReglasComisionNoEncontradas(Exception):
    """Raised when no commission rules exist for the given client type."""
