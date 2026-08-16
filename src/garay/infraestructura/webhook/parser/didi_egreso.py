"""DiDi ride-receipt email parser."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal

from garay.infraestructura.webhook.html_texto import html_a_texto
from garay.infraestructura.webhook.parser.base import (
    BANCO_DIDI,
    ErrorParseoBanco,
    ParserEgreso,
)
from garay.infraestructura.webhook.schemas import EgresoExtraido

# Pattern: "Total  $12.800" — dot as thousands separator, no decimals.
# Anchored on the word "Total" to skip sub-total adjustment lines above it.
_PATRON_TOTAL = re.compile(
    r"\bTotal\b[^0-9]*\$([\d.]+)",
    re.IGNORECASE,
)

# Pattern: "vie, 31 jul, 2026" — Spanish weekday prefix, day, 3-letter month, year.
_PATRON_FECHA = re.compile(
    r"\b\w+,\s+(\d{1,2})\s+(\w{3}),\s+(\d{4})\b",
    re.IGNORECASE,
)

_MESES_ES: dict[str, int] = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}


def _parsear_monto_didi(texto: str) -> Decimal:
    """Extract amount from 'Total  $12.800' — last match wins (net total)."""
    coincidencias = _PATRON_TOTAL.findall(texto)
    if not coincidencias:
        raise ErrorParseoBanco("No se encontro linea 'Total $' en email DiDi")
    monto_str = coincidencias[-1].replace(".", "")
    return Decimal(monto_str)


def _parsear_fecha_didi(texto: str) -> datetime:
    """Extract date from 'vie, 31 jul, 2026' format and return UTC datetime."""
    coincidencia = _PATRON_FECHA.search(texto)
    if coincidencia is None:
        raise ErrorParseoBanco(
            "No se encontro fecha 'weekday, DD mes, YYYY' en email DiDi"
        )
    try:
        dia = int(coincidencia.group(1))
        mes_key = coincidencia.group(2).lower()[:3]
        mes = _MESES_ES[mes_key]
        anio = int(coincidencia.group(3))
    except (KeyError, ValueError) as error:
        raise ErrorParseoBanco(
            f"Fecha invalida en email DiDi: '{coincidencia.group(0)}'"
        ) from error
    return datetime(anio, mes, dia, tzinfo=UTC)


class ParserDiDiEgreso(ParserEgreso):
    """Parse a DiDi ride-receipt email into an EgresoExtraido."""

    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> EgresoExtraido:
        texto = cuerpo_texto or html_a_texto(cuerpo_html)
        # Collapse NBSP and extra whitespace so patterns match consistently.
        texto = re.sub(r"\s+", " ", texto)

        monto = _parsear_monto_didi(texto)
        fecha_egreso = _parsear_fecha_didi(texto)

        return EgresoExtraido(
            monto=monto,
            descripcion="Viaje DiDi",
            banco_origen=BANCO_DIDI,
            fecha_egreso=fecha_egreso,
        )
