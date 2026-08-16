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
# The bounded gap [^0-9]{0,10} prevents spanning from "Total $12.800" across
# footer text like "Total ahorrado este mes $50.000" (30+ chars apart after
# whitespace collapse).  "\bTotal\b" blocks "Subtotal".
# Uses re.search (first match) — the real Total always appears before any footer.
_PATRON_TOTAL = re.compile(
    r"\bTotal\b[^0-9]{0,10}\$([\d.]+)",
    re.IGNORECASE,
)

# Pattern: "vie, 31 jul, 2026" — Spanish weekday prefix, day, 3-letter month, year.
# Uses re.search (first match) — the trip date always appears before footer dates.
_PATRON_FECHA = re.compile(
    r"\b\w+,\s+(\d{1,2})\s+(\w{3}),\s+(\d{4})\b",
    re.IGNORECASE,
)

# Spanish 3-letter month map — covers all 12 abbreviations used in DiDi receipts.
# NOTE: nequi_egreso.py has an identical map; dedup into base.py is deferred to a
# separate cleanup PR to avoid touching unrelated working code.
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
    """Extract amount from 'Total  $12.800' — first match wins (net total).

    Using search (not findall[-1]) so a footer line that is farther from the
    'Total' label is never picked over the real total that appears first.
    """
    coincidencia = _PATRON_TOTAL.search(texto)
    if coincidencia is None:
        raise ErrorParseoBanco("No se encontro linea 'Total $' en email DiDi")
    monto_str = coincidencia.group(1).replace(".", "")
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
