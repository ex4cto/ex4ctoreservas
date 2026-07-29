"""Bancolombia outgoing-payment email parser."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from garay.infraestructura.webhook.parser.base import (
    BANCO_BANCOLOMBIA,
    ErrorParseoBanco,
    ParserEgreso,
    _parsear_fecha_hora_bancolombia,
)
from garay.infraestructura.webhook.schemas import EgresoExtraido

# Pattern: "Compraste $69.328,00 en MOVISTAR PAGOSEPAYCO con tu T.Deb"
_PATRON_COMPRA = re.compile(
    r"Compraste\s+\$([\d.,]+)\s+en\s+(.+?)\s+con\s+tu\s+T\.Deb",
    re.IGNORECASE,
)

# Pattern for date/time used by compra and transferencia-cuenta:
# "el 27/07/2026 a las 18:25"
_PATRON_FECHA_EL = re.compile(
    r"el\s+(\d{2}/\d{2}/\d{2,4})\s+a\s+las\s+(\d{2}:\d{2})"
)

# Pattern: "Transferiste $50,000.00 desde tu cuenta 7488 a la cuenta *3207904880"
_PATRON_TRANSFERENCIA_CUENTA = re.compile(
    r"Transferiste\s+\$([\d.,]+)\s+desde\s+tu\s+cuenta\s+[\d]+\s+a\s+la\s+cuenta\s+\*([\d]+)",
    re.IGNORECASE,
)

# Pattern: "transferiste $6,000.00 a la llave ... desde tu cuenta *7488 a NEIDA GARCIA
#            el 25/07/26 a las 16:26"
_PATRON_TRANSFERENCIA_BREB = re.compile(
    r"transferiste\s+\$([\d.,]+)\s+a\s+la\s+llave\s+[\d]+\s+desde\s+tu\s+cuenta"
    r"\s+\*[\d]+\s+a\s+(.+?)\s+el\s+(\d{2}/\d{2}/\d{2,4})\s+a\s+las\s+(\d{2}:\d{2})",
    re.IGNORECASE,
)


def _parsear_monto_bilingue(texto: str) -> Decimal:
    """Parse a monetary amount that may use Colombian or US number formatting.

    Colombian: $69.328,00  →  dots=thousands, comma=decimal  →  69328.00
    US:        $50,000.00  →  commas=thousands, dot=decimal  →  50000.00
    Nequi:     5.000       →  dot=thousands (3 digits after)  →  5000
    Plain:     100         →  no separators                  →  100
    """
    limpio = texto.strip().lstrip("$").strip()

    last_comma = limpio.rfind(",")
    last_dot = limpio.rfind(".")

    if last_comma > last_dot:
        # Colombian format: comma is decimal separator
        sin_miles = limpio.replace(".", "")
        normalizado = sin_miles.replace(",", ".")
    elif last_dot > last_comma and last_comma >= 0:
        # US format: dot is decimal separator, comma is thousands
        normalizado = limpio.replace(",", "")
    elif last_dot >= 0 and last_comma < 0:
        # Only dots — check if it's thousands separator (3 digits after last dot)
        parte_decimal = limpio[last_dot + 1 :]
        # If 3 digits after dot: thousands separator; otherwise: decimal separator.
        normalizado = limpio.replace(".", "") if len(parte_decimal) == 3 else limpio
    else:
        # Plain integer, no separators
        normalizado = limpio

    try:
        return Decimal(normalizado)
    except InvalidOperation as error:
        raise ErrorParseoBanco(f"Monto invalido: '{texto}'") from error



class ParserBancolombiaEgreso(ParserEgreso):
    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> EgresoExtraido:
        texto = cuerpo_texto or cuerpo_html

        # Try Tipo 3: Bre-B transfer (must check before Tipo 2 to avoid partial matches)
        m = _PATRON_TRANSFERENCIA_BREB.search(texto)
        if m:
            monto = _parsear_monto_bilingue(m.group(1))
            destinatario = m.group(2).strip()
            fecha_egreso = _parsear_fecha_hora_bancolombia(m.group(3), m.group(4))
            return EgresoExtraido(
                monto=monto,
                descripcion=f"Transferencia a {destinatario}",
                banco_origen=BANCO_BANCOLOMBIA,
                fecha_egreso=fecha_egreso,
            )

        # Try Tipo 1: Compra tarjeta debito
        m = _PATRON_COMPRA.search(texto)
        if m:
            monto = _parsear_monto_bilingue(m.group(1))
            comercio = m.group(2).strip()
            fecha_m = _PATRON_FECHA_EL.search(texto)
            if fecha_m is None:
                raise ErrorParseoBanco("No se encontro fecha en email de compra Bancolombia")
            fecha_egreso = _parsear_fecha_hora_bancolombia(fecha_m.group(1), fecha_m.group(2))
            return EgresoExtraido(
                monto=monto,
                descripcion=f"Compra en {comercio}",
                banco_origen=BANCO_BANCOLOMBIA,
                fecha_egreso=fecha_egreso,
            )

        # Try Tipo 2: Transferencia a cuenta bancaria
        m = _PATRON_TRANSFERENCIA_CUENTA.search(texto)
        if m:
            monto = _parsear_monto_bilingue(m.group(1))
            cuenta = m.group(2).strip()
            fecha_m = _PATRON_FECHA_EL.search(texto)
            if fecha_m is None:
                raise ErrorParseoBanco(
                    "No se encontro fecha en email de transferencia Bancolombia"
                )
            fecha_egreso = _parsear_fecha_hora_bancolombia(fecha_m.group(1), fecha_m.group(2))
            return EgresoExtraido(
                monto=monto,
                descripcion=f"Transferencia a cuenta *{cuenta}",
                banco_origen=BANCO_BANCOLOMBIA,
                fecha_egreso=fecha_egreso,
            )

        raise ErrorParseoBanco(
            "No se encontro patron de egreso en email Bancolombia"
        )
