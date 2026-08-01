"""Bancolombia bank email parser."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from garay.infraestructura.webhook.html_texto import html_a_texto
from garay.infraestructura.webhook.parser.base import (
    BANCO_BANCOLOMBIA,
    ErrorParseoBanco,
    ParserBanco,
    _parsear_fecha_hora_bancolombia,
)
from garay.infraestructura.webhook.schemas import PagoExtraido

# Bancolombia-to-Bancolombia: "por $X de NOMBRE en tu cuenta ... el fecha a las hora"
_PATRON_BC_A_BC = re.compile(
    r"recibiste\s+una\s+transferencia\s+por\s+\$([\d,\.]+)\s+de\s+(.+?)\s+en\s+tu\s+cuenta"
    r".+?el\s+(\d{2}/\d{2}/\d{2,4})\s+a\s+las\s+(\d{2}:\d{2})",
    re.IGNORECASE | re.DOTALL,
)

# External bank to Bancolombia: "de NOMBRE por $X el fecha a las hora"
_PATRON_EXTERNO = re.compile(
    r"recibiste\s+una\s+transferencia\s+de\s+(.+?)\s+por\s+\$([\d,\.]+)"
    r".+?el\s+(\d{2}/\d{2}/\d{2,4})\s+a\s+las\s+(\d{2}:\d{2})",
    re.IGNORECASE | re.DOTALL,
)

# Provider/gateway payment (e.g. Wompi payment link):
# "Recibiste un pago PROVEEDOR de WOMPI S.A.S. por $208,929.30 en tu cuenta ...
#  el 30/07/2026 a las 12:06"
_PATRON_PAGO_PROVEEDOR = re.compile(
    r"recibiste\s+un\s+pago(?:\s+\w+)?\s+de\s+(.+?)\s+por\s+\$([\d,\.]+)"
    r"\s+en\s+tu\s+cuenta.+?el\s+(\d{2}/\d{2}/\d{2,4})\s+a\s+las\s+(\d{2}:\d{2})",
    re.IGNORECASE | re.DOTALL,
)
# Cash deposit at a banking correspondent (no "a las" — date and time run together):
# "Recibiste una consignacion por $20,000 desde el corresponsal OPRAP BOCAGRANDE 1
#  en CARTAGENA DE IN, el 15/07/26 16:47"
_PATRON_CONSIGNACION = re.compile(
    r"recibiste\s+una\s+consignaci[oó]n\s+por\s+\$([\d,\.]+)\s+desde\s+el\s+corresponsal\s+(.+?)"
    r"\s+en\s+.+?\s+el\s+(\d{2}/\d{2}/\d{2,4})\s+(\d{2}:\d{2})",
    re.IGNORECASE | re.DOTALL,
)
def _parsear_monto(texto: str) -> Decimal:
    sin_comas = texto.replace(",", "")
    try:
        return Decimal(sin_comas)
    except InvalidOperation as error:
        raise ErrorParseoBanco(f"Monto invalido Bancolombia: '{texto}'") from error


class ParserBancolombia(ParserBanco):
    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> PagoExtraido:
        texto = cuerpo_texto or html_a_texto(cuerpo_html)

        m = _PATRON_BC_A_BC.search(texto)
        if m:
            monto = _parsear_monto(m.group(1))
            remitente = m.group(2).strip()
            fecha_pago = _parsear_fecha_hora_bancolombia(m.group(3), m.group(4))
        elif (m2 := _PATRON_EXTERNO.search(texto)) is not None:
            remitente = m2.group(1).strip()
            monto = _parsear_monto(m2.group(2))
            fecha_pago = _parsear_fecha_hora_bancolombia(m2.group(3), m2.group(4))
        elif (m3 := _PATRON_PAGO_PROVEEDOR.search(texto)) is not None:
            remitente = m3.group(1).strip()
            monto = _parsear_monto(m3.group(2))
            fecha_pago = _parsear_fecha_hora_bancolombia(m3.group(3), m3.group(4))
        elif (m4 := _PATRON_CONSIGNACION.search(texto)) is not None:
            monto = _parsear_monto(m4.group(1))
            remitente = f"Corresponsal {m4.group(2).strip()}"
            fecha_pago = _parsear_fecha_hora_bancolombia(m4.group(3), m4.group(4))
        else:
            raise ErrorParseoBanco(
                "No se encontro patron de pago recibido en email Bancolombia"
            )
        return PagoExtraido(
            monto=monto,
            remitente=remitente,
            banco_origen=BANCO_BANCOLOMBIA,
            fecha_pago=fecha_pago,
        )
