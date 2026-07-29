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

_PATRON_RECIBIDO = re.compile(
    r"recibiste\s+una\s+transferencia\s+de\s+(.+?)\s+por\s+\$([\d,]+(?:\.\d{2})?)"
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
        coincidencia = _PATRON_RECIBIDO.search(texto)
        if not coincidencia:
            raise ErrorParseoBanco(
                "No se encontro patron de pago recibido en email Bancolombia"
            )
        remitente = coincidencia.group(1).strip()
        monto = _parsear_monto(coincidencia.group(2))
        fecha_pago = _parsear_fecha_hora_bancolombia(coincidencia.group(3), coincidencia.group(4))
        return PagoExtraido(
            monto=monto,
            remitente=remitente,
            banco_origen=BANCO_BANCOLOMBIA,
            fecha_pago=fecha_pago,
        )
