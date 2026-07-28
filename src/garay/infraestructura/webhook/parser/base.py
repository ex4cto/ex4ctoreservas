"""Abstract base for bank email parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from garay.infraestructura.webhook.schemas import PagoExtraido

BANCO_BANCOLOMBIA = "Bancolombia"
BANCO_NEQUI = "Nequi"

_DOMINIOS_BANCOLOMBIA: frozenset[str] = frozenset(
    [
        "notificacionesbancolombia.com",
        "bancolombia.com.co",
        "an.notificacionesbancolombia.com",
    ]
)
_DOMINIOS_NEQUI: frozenset[str] = frozenset(["nequi.com.co"])


class ErrorParseoBanco(Exception):
    """Raised when a bank email cannot be parsed into a PagoExtraido."""


class ParserBanco(ABC):
    @abstractmethod
    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> PagoExtraido:
        ...


def detectar_banco(remitente_email: str) -> str | None:
    """Return the bank name for a sender email address, or None if unknown."""
    dominio = remitente_email.lower().split("@")[-1]
    if dominio in _DOMINIOS_BANCOLOMBIA:
        return BANCO_BANCOLOMBIA
    if dominio in _DOMINIOS_NEQUI:
        return BANCO_NEQUI
    return None
