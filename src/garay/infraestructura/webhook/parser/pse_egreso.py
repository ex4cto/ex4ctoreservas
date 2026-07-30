"""PSE (ACH Colombia) outgoing-payment email parser."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from garay.infraestructura.webhook.parser.bancolombia_egreso import _parsear_monto_bilingue
from garay.infraestructura.webhook.parser.base import (
    BANCO_PSE,
    ErrorParseoBanco,
    ParserEgreso,
)
from garay.infraestructura.webhook.schemas import EgresoExtraido

# Pattern: "Valor: $ 124.200,00" (with optional spaces around $)
_PATRON_VALOR = re.compile(r"Valor:\s*\$?\s*([\d.,]+)", re.IGNORECASE)

# Pattern: "Empresa: WOMPI S.A.S Descripción:"  or  "Empresa: WOMPI S.A.S Fecha"
_PATRON_EMPRESA = re.compile(
    r"Empresa:\s*(.+?)\s+(?:Descripci[oó]n|Fecha)",
    re.IGNORECASE,
)

# Pattern: "Fecha de la transacción: 06/07/2026"
_PATRON_FECHA = re.compile(
    r"Fecha de la transacci[oó]n:\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)


class ParserPSEEgreso(ParserEgreso):
    def parsear(self, cuerpo_html: str, cuerpo_texto: str) -> EgresoExtraido:
        texto_raw = cuerpo_texto or cuerpo_html
        # Normalize NBSP and extra whitespace — same pattern as Nequi parser
        texto = re.sub(r"\s+", " ", texto_raw)

        m_valor = _PATRON_VALOR.search(texto)
        if m_valor is None:
            raise ErrorParseoBanco(
                "No se encontro patron de egreso en email PSE"
            )
        monto = _parsear_monto_bilingue(m_valor.group(1))

        m_empresa = _PATRON_EMPRESA.search(texto)
        if m_empresa is None:
            raise ErrorParseoBanco(
                "No se encontro patron de egreso en email PSE"
            )
        empresa = m_empresa.group(1).strip()

        m_fecha = _PATRON_FECHA.search(texto)
        if m_fecha is None:
            raise ErrorParseoBanco(
                "No se encontro patron de egreso en email PSE"
            )
        fecha_egreso = datetime.strptime(m_fecha.group(1), "%d/%m/%Y").replace(
            tzinfo=UTC
        )

        return EgresoExtraido(
            monto=monto,
            descripcion=f"Pago PSE a {empresa}",
            banco_origen=BANCO_PSE,
            fecha_egreso=fecha_egreso,
        )
