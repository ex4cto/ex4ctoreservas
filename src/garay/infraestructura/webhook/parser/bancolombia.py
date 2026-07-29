"""Bancolombia bank email parser."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

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
_PATRON_ETIQUETAS_HTML = re.compile(r"<[^>]+>")


def _texto_desde_html(html: str) -> str:
    sin_etiquetas = _PATRON_ETIQUETAS_HTML.sub(" ", html)
    return " ".join(sin_etiquetas.split())


def _parsear_monto(texto: str) -> Decimal:
    sin_comas = texto.replace(",", "")
    try:
        return Decimal(sin_comas)
    except InvalidOperation as error:
        raise ErrorParseoBanco(f"Monto invalido Bancolombia: '{texto}'") from error


class ParserBancolombia(ParserBanco):
    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> PagoExtraido:
        texto = cuerpo_texto or _texto_desde_html(cuerpo_html)

        m = _PATRON_BC_A_BC.search(texto)
        if m:
            monto = _parsear_monto(m.group(1))
            remitente = m.group(2).strip()
            fecha_pago = _parsear_fecha_hora_bancolombia(m.group(3), m.group(4))
        else:
            m2 = _PATRON_EXTERNO.search(texto)
            if not m2:
                raise ErrorParseoBanco(
                    "No se encontro patron de pago recibido en email Bancolombia"
                )
            remitente = m2.group(1).strip()
            monto = _parsear_monto(m2.group(2))
            fecha_pago = _parsear_fecha_hora_bancolombia(m2.group(3), m2.group(4))
        return PagoExtraido(
            monto=monto,
            remitente=remitente,
            banco_origen=BANCO_BANCOLOMBIA,
            fecha_pago=fecha_pago,
        )
