"""Nequi outgoing-payment email parser."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from garay.infraestructura.webhook.parser.bancolombia_egreso import _parsear_monto_bilingue
from garay.infraestructura.webhook.parser.base import (
    _MESES_ES_FULL,
    BANCO_NEQUI,
    ErrorParseoBanco,
    ParserEgreso,
)
from garay.infraestructura.webhook.schemas import EgresoExtraido

# Pattern: "Enviaste de manera exitosa 5.000 a la llave 1047487553 de BRYAN CASTRO
#            el 25 de julio de 2026 a las 7:05 p.m."
_PATRON_ENVIO = re.compile(
    r"Enviaste de manera exitosa\s+([\d.,]+)\s+a la llave\s+\S+\s+de\s+(.+?)"
    r"\s+el\s+(\d{1,2} de \w+ de \d{4})\s+a\s+las?\s+(\d{1,2}:\d{2}\s+[ap]\.m\.?)",
    re.IGNORECASE,
)

# Pattern: "Pagaste con Nequi tu factura por $3.000"
_PATRON_FACTURA = re.compile(
    r"Pagaste con Nequi tu factura por\s+\$([\d.,]+)",
    re.IGNORECASE,
)

# Pattern: "Hiciste un pago en Kushki Colombia SA por $100.000"
_PATRON_PAGO_COMERCIO = re.compile(
    r"Hiciste un pago en (.+?) por \$([\d.,]+)",
    re.IGNORECASE,
)

# Pattern: "Fecha: El 13 de junio de 2026"
_PATRON_FECHA_EL = re.compile(
    r"Fecha:\s+[Ee]l\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)

# Pattern: "Hora: 4:46 p. m."
_PATRON_HORA_SEPARADA = re.compile(
    r"Hora:\s+(\d{1,2}:\d{2})\s+([ap])\.\s*m\.",
    re.IGNORECASE,
)

# Pattern: "Fecha: 25/Jul/2026"
_PATRON_FECHA_FACTURA = re.compile(
    r"Fecha:\s+(\d{1,2}/(\w{3})/(\d{4}))",
    re.IGNORECASE,
)

_MESES_ES: dict[str, int] = {
    "ene": 1,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
    "dec": 12,
}


def _parsear_fecha_hora_envio(fecha_str: str, hora_str: str) -> datetime:
    """Parse Nequi Bre-B date: '25 de julio de 2026' + '7:05 p.m.'"""
    partes = fecha_str.lower().split()
    try:
        dia = int(partes[0])
        mes = _MESES_ES_FULL[partes[2]]
        anio = int(partes[4])
    except (IndexError, KeyError, ValueError) as error:
        raise ErrorParseoBanco(f"Fecha invalida Nequi envio: '{fecha_str}'") from error

    hora_limpia = hora_str.replace(".", "").strip()
    partes_hora = hora_limpia.split()
    try:
        h, m = map(int, partes_hora[0].split(":"))
        periodo = partes_hora[1].lower()
    except (IndexError, ValueError) as error:
        raise ErrorParseoBanco(f"Hora invalida Nequi envio: '{hora_str}'") from error

    if periodo == "pm" and h != 12:
        h += 12
    elif periodo == "am" and h == 12:
        h = 0

    return datetime(anio, mes, dia, h, m, tzinfo=UTC)


def _parsear_fecha_hora_comercio(texto: str) -> datetime:
    """Parse date and time from commerce-payment body.

    Expects separate lines:
        Fecha: El 13 de junio de 2026
        Hora: 4:46 p. m.
    """
    m_fecha = _PATRON_FECHA_EL.search(texto)
    if m_fecha is None:
        raise ErrorParseoBanco("No se encontro fecha en email de pago comercio Nequi")

    m_hora = _PATRON_HORA_SEPARADA.search(texto)
    if m_hora is None:
        raise ErrorParseoBanco("No se encontro hora en email de pago comercio Nequi")

    try:
        dia = int(m_fecha.group(1))
        mes = _MESES_ES_FULL[m_fecha.group(2).lower()]
        anio = int(m_fecha.group(3))
    except (KeyError, ValueError) as error:
        raise ErrorParseoBanco(
            f"Fecha invalida Nequi comercio: '{m_fecha.group(0)}'"
        ) from error

    try:
        h, minuto = map(int, m_hora.group(1).split(":"))
        periodo = m_hora.group(2).lower()
    except (IndexError, ValueError) as error:
        raise ErrorParseoBanco(
            f"Hora invalida Nequi comercio: '{m_hora.group(0)}'"
        ) from error

    if periodo == "p" and h != 12:
        h += 12
    elif periodo == "a" and h == 12:
        h = 0

    return datetime(anio, mes, dia, h, minuto, tzinfo=UTC)


def _parsear_fecha_factura(fecha_str: str) -> datetime:
    """Parse Nequi invoice date: '25/Jul/2026'"""
    partes = fecha_str.split("/")
    try:
        dia = int(partes[0])
        mes_key = partes[1].lower()[:3]
        mes = _MESES_ES[mes_key]
        anio = int(partes[2])
    except (IndexError, KeyError, ValueError) as error:
        raise ErrorParseoBanco(f"Fecha invalida Nequi factura: '{fecha_str}'") from error

    return datetime(anio, mes, dia, 0, 0, tzinfo=UTC)


class ParserNequiEgreso(ParserEgreso):
    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> EgresoExtraido:
        # Forwarded emails carry NBSP (\xa0) and line breaks; collapse whitespace
        # so the literal-space patterns match.
        texto = re.sub(r"\s+", " ", cuerpo_texto or cuerpo_html)

        # Try Tipo 1: Envio Bre-B
        m = _PATRON_ENVIO.search(texto)
        if m:
            monto = _parsear_monto_bilingue(m.group(1))
            destinatario = m.group(2).strip()
            fecha_egreso = _parsear_fecha_hora_envio(m.group(3), m.group(4))
            return EgresoExtraido(
                monto=monto,
                descripcion=f"Envio a {destinatario}",
                banco_origen=BANCO_NEQUI,
                fecha_egreso=fecha_egreso,
            )

        # Try Tipo 2: Pago factura
        m_factura = _PATRON_FACTURA.search(texto)
        if m_factura:
            monto = _parsear_monto_bilingue(m_factura.group(1))
            m_fecha = _PATRON_FECHA_FACTURA.search(texto)
            if m_fecha is None:
                raise ErrorParseoBanco(
                    "No se encontro fecha en email de factura Nequi"
                )
            fecha_egreso = _parsear_fecha_factura(m_fecha.group(1))
            return EgresoExtraido(
                monto=monto,
                descripcion="Pago factura Nequi",
                banco_origen=BANCO_NEQUI,
                fecha_egreso=fecha_egreso,
            )

        # Try Tipo 3: Pago a comercio
        m_comercio = _PATRON_PAGO_COMERCIO.search(texto)
        if m_comercio:
            monto = _parsear_monto_bilingue(m_comercio.group(2))
            comercio = m_comercio.group(1).strip()
            fecha_egreso = _parsear_fecha_hora_comercio(texto)
            return EgresoExtraido(
                monto=monto,
                descripcion=f"Pago en {comercio}",
                banco_origen=BANCO_NEQUI,
                fecha_egreso=fecha_egreso,
            )

        raise ErrorParseoBanco(
            "No se encontro patron de egreso en email Nequi"
        )
