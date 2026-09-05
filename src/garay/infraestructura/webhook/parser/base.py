"""Abstract base for bank email parsers."""

from __future__ import annotations

import datetime
import re
from abc import ABC, abstractmethod
from datetime import UTC
from typing import Final

from garay.dominio.conciliacion.categorias import CATEGORIA_TRANSPORTE, banco_a_categoria
from garay.infraestructura.webhook.schemas import EgresoExtraido, PagoExtraido

BANCO_BANCOLOMBIA = "Bancolombia"
BANCO_NEQUI = "Nequi"
BANCO_PSE = "PSE"
BANCO_UBER: Final[str] = "Uber"
BANCO_DIDI: Final[str] = "DiDi"

DIRECCION_INGRESO: Final = "ingreso"
DIRECCION_EGRESO: Final = "egreso"

_DOMINIOS_BANCOLOMBIA: frozenset[str] = frozenset(
    [
        "notificacionesbancolombia.com",
        "bancolombia.com.co",
        "an.notificacionesbancolombia.com",
    ]
)
_DOMINIOS_NEQUI: frozenset[str] = frozenset(["nequi.com.co"])
_DOMINIOS_UBER: frozenset[str] = frozenset(["uber.com"])
_DOMINIOS_DIDI: frozenset[str] = frozenset(["co.didiglobal.com"])

_MESES_ES_FULL: dict[str, int] = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_KEYWORDS_EGRESO: frozenset[str] = frozenset(
    [
        "compraste",
        "transferiste",
        "enviaste",
        "pagaste con nequi",
    ]
)


class ErrorParseoBanco(Exception):
    """Raised when a bank email cannot be parsed into a PagoExtraido."""


def _parsear_fecha_hora_bancolombia(fecha_str: str, hora_str: str) -> datetime.datetime:
    """Parse a Bancolombia date/time string pair into a UTC datetime.

    Tries both two-digit and four-digit year formats.
    Raises ErrorParseoBanco if neither format matches.
    """
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(
                f"{fecha_str} {hora_str}", f"{fmt} %H:%M"
            ).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ErrorParseoBanco(
        f"Fecha/hora invalida Bancolombia: '{fecha_str} {hora_str}'"
    )


class ParserBanco(ABC):
    @abstractmethod
    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> PagoExtraido:
        ...


class ParserEgreso(ABC):
    @abstractmethod
    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> EgresoExtraido:
        ...


_SENALES_TRANSACCION: frozenset[str] = frozenset(
    [
        "recibiste",
        "transferiste",
        "compraste",
        "enviaste",
        "pagaste con nequi",
        "hiciste un pago",
        "consignaci",
    ]
)


def es_transaccion(cuerpo: str) -> bool:
    """Return True if the email body contains at least one transaction signal.

    Conservative gate: only returns False when NO transaction signal is present.
    If any signal is found, the email is treated as a transaction and normal
    parsing continues (parse → quarantine on failure).

    Signals cover every bank verb used by the Nequi, Bancolombia, and PSE
    parsers, plus the existing PSE body markers via ``_es_pse``.
    """
    cuerpo_lower = " ".join(cuerpo.lower().split())
    if any(senal in cuerpo_lower for senal in _SENALES_TRANSACCION):
        return True
    return _es_pse(cuerpo_lower)


def _es_pse(cuerpo_lower: str) -> bool:
    """Return True if the email body contains strong PSE markers."""
    if "serviciopse" in cuerpo_lower or "achcolombia" in cuerpo_lower:
        return True
    if "pse - transacci" in cuerpo_lower or "pse - transaccion" in cuerpo_lower:
        return True
    # "cus:" is PSE's transaction-reference label (CUS: 455692497); specific
    # enough to avoid false positives from substrings like "excusa" + "pse".
    return "cus:" in cuerpo_lower


def _dominio_coincide(dominio: str, dominios: frozenset[str]) -> bool:
    """Return True if dominio equals or is a subdomain of any entry in dominios."""
    return any(
        dominio == d or dominio.endswith("." + d) for d in dominios
    )


def detectar_banco(remitente_email: str, cuerpo: str = "") -> str | None:
    """Return the bank name for a sender email, or None if unknown.

    Falls back to body content when the email was forwarded through Gmail
    and the original bank sender address was replaced.
    """
    dominio = remitente_email.lower().split("@")[-1]
    if dominio in _DOMINIOS_BANCOLOMBIA:
        return BANCO_BANCOLOMBIA
    if dominio in _DOMINIOS_NEQUI:
        return BANCO_NEQUI
    if _dominio_coincide(dominio, _DOMINIOS_UBER):
        return BANCO_UBER
    if _dominio_coincide(dominio, _DOMINIOS_DIDI):
        return BANCO_DIDI

    cuerpo_lower = cuerpo.lower()
    if _es_pse(cuerpo_lower):
        return BANCO_PSE
    if "bancolombia" in cuerpo_lower:
        return BANCO_BANCOLOMBIA
    if "nequi" in cuerpo_lower:
        return BANCO_NEQUI

    return None


# A real transport receipt always states a charged amount: Uber uses
# "COP 10,700" and DiDi uses "$12.800".  Marketing/promo emails from the same
# domains carry no charged amount, so the absence of this pattern is the signal
# to drop the email silently instead of routing it to the parser (which would
# fail and raise a noisy 'Correo no parseado' dev alert).
_PATRON_MONTO_TRANSPORTE: Final = re.compile(r"COP\s*[\d.,]+|\$\s*[\d.,]+")


def es_recibo_transporte(cuerpo: str) -> bool:
    """Return True if a transport-bank email looks like a real ride receipt.

    Conservative gate mirroring ``es_transaccion``: a receipt always states a
    charged amount (Uber ``COP 10,700``, DiDi ``$12.800``).  Promotional or
    marketing emails carry no charged amount, so they return False and are
    dropped silently upstream instead of being quarantined and alerted.

    Lenient on purpose: any charged amount passes the gate, so a real receipt
    whose ``Total`` line format changed still reaches the parser, fails, and is
    quarantined + alerted — the signal we want when Uber/DiDi change formats.
    """
    return bool(_PATRON_MONTO_TRANSPORTE.search(cuerpo))


def es_banco_transporte(banco: str | None) -> bool:
    """Return True if banco is a transport-service bank (Uber or DiDi).

    Accepts None safely — returns False without raising.
    Delegates to the domain's banco_a_categoria so categorias.py
    is the single source of truth for which banks are transport.
    """
    return banco is not None and banco_a_categoria(banco) == CATEGORIA_TRANSPORTE


def detectar_direccion(cuerpo_texto: str) -> str:
    """Return DIRECCION_EGRESO or DIRECCION_INGRESO based on keywords in email body."""
    texto_lower = cuerpo_texto.lower()
    if _es_pse(texto_lower):
        return DIRECCION_EGRESO
    if any(kw in texto_lower for kw in _KEYWORDS_EGRESO):
        return DIRECCION_EGRESO
    return DIRECCION_INGRESO
