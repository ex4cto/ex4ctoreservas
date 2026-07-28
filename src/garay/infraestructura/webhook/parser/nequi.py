"""Nequi bank email parser."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from garay.infraestructura.webhook.parser.base import (
    BANCO_NEQUI,
    ErrorParseoBanco,
    ParserBanco,
)
from garay.infraestructura.webhook.schemas import PagoExtraido

_PATRON_RECIBIDO = re.compile(
    r"Recibiste ([\d.]+(?:,\d{2})?) de (.+?) el (\d{1,2} de \w+ de \d{4})"
    r" a las (\d{1,2}:\d{2} [ap]\.m\.?)",
    re.IGNORECASE,
)

_MESES_ES: dict[str, int] = {
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


def _parsear_monto_nequi(texto: str) -> Decimal:
    partes = texto.split(",")
    entero = partes[0].replace(".", "")
    decimal_parte = partes[1] if len(partes) > 1 else "00"
    try:
        return Decimal(f"{entero}.{decimal_parte}")
    except InvalidOperation as error:
        raise ErrorParseoBanco(f"Monto invalido Nequi: '{texto}'") from error


def _parsear_fecha_hora_nequi(fecha_str: str, hora_str: str) -> datetime:
    partes_fecha = fecha_str.lower().split()
    try:
        dia = int(partes_fecha[0])
        mes = _MESES_ES[partes_fecha[2]]
        anio = int(partes_fecha[4])
    except (IndexError, KeyError, ValueError) as error:
        raise ErrorParseoBanco(f"Fecha invalida Nequi: '{fecha_str}'") from error
    partes_hora = hora_str.replace(".", "").split()
    try:
        h, m = map(int, partes_hora[0].split(":"))
        periodo = partes_hora[1].lower()
    except (IndexError, ValueError) as error:
        raise ErrorParseoBanco(f"Hora invalida Nequi: '{hora_str}'") from error
    if periodo == "pm" and h != 12:
        h += 12
    elif periodo == "am" and h == 12:
        h = 0
    return datetime(anio, mes, dia, h, m, tzinfo=UTC)


class ParserNequi(ParserBanco):
    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> PagoExtraido:
        coincidencia = _PATRON_RECIBIDO.search(cuerpo_texto)
        if not coincidencia:
            raise ErrorParseoBanco(
                "No se encontro patron de pago recibido en email Nequi"
            )
        monto = _parsear_monto_nequi(coincidencia.group(1))
        remitente = coincidencia.group(2).strip().rstrip(",")
        fecha_pago = _parsear_fecha_hora_nequi(coincidencia.group(3), coincidencia.group(4))
        return PagoExtraido(
            monto=monto,
            remitente=remitente,
            banco_origen=BANCO_NEQUI,
            fecha_pago=fecha_pago,
        )
