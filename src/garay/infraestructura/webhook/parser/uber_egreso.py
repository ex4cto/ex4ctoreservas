"""Uber ride-receipt email parser."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal

from garay.infraestructura.webhook.html_texto import html_a_texto
from garay.infraestructura.webhook.parser.base import (
    BANCO_UBER,
    ErrorParseoBanco,
    ParserEgreso,
)
from garay.infraestructura.webhook.schemas import EgresoExtraido

# Pattern: "Total  COP 10,700" — comma as thousands separator, no decimals.
# Anchored on the word "Total" to skip sub-total adjustment lines above it.
_PATRON_TOTAL = re.compile(
    r"\bTotal\b[^0-9]*COP\s+([\d,]+)",
    re.IGNORECASE,
)

# Pattern: "07/08/2026" — DD/MM/YYYY
_PATRON_FECHA = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")


def _parsear_monto_uber(texto: str) -> Decimal:
    """Extract amount from 'Total  COP 10,700' — last match wins (net total)."""
    coincidencias = _PATRON_TOTAL.findall(texto)
    if not coincidencias:
        raise ErrorParseoBanco("No se encontro linea 'Total COP' en email Uber")
    monto_str = coincidencias[-1].replace(",", "")
    return Decimal(monto_str)


def _parsear_fecha_uber(texto: str) -> datetime:
    """Extract date from 'DD/MM/YYYY' format and return a UTC-aware datetime."""
    coincidencia = _PATRON_FECHA.search(texto)
    if coincidencia is None:
        raise ErrorParseoBanco("No se encontro fecha DD/MM/YYYY en email Uber")
    try:
        return datetime.strptime(coincidencia.group(1), "%d/%m/%Y").replace(tzinfo=UTC)
    except ValueError as error:
        raise ErrorParseoBanco(
            f"Fecha invalida en email Uber: '{coincidencia.group(1)}'"
        ) from error


class ParserUberEgreso(ParserEgreso):
    """Parse an Uber ride-receipt email into an EgresoExtraido."""

    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> EgresoExtraido:
        texto = cuerpo_texto or html_a_texto(cuerpo_html)
        # Collapse NBSP and extra whitespace so patterns match consistently.
        texto = re.sub(r"\s+", " ", texto)

        monto = _parsear_monto_uber(texto)
        fecha_egreso = _parsear_fecha_uber(texto)

        return EgresoExtraido(
            monto=monto,
            descripcion="Viaje Uber",
            banco_origen=BANCO_UBER,
            fecha_egreso=fecha_egreso,
        )
