"""Concrete adapter: ExtractorIA backed by the Anthropic Claude vision API."""

from __future__ import annotations

import base64
import datetime
import json
import logging
from decimal import Decimal, InvalidOperation

import anthropic
from anthropic.types import TextBlock

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.servicios_externos import ExtractorIA
from garay.dominio.tiquetera.valor_objetos import DatosExtraidos

_logger = logging.getLogger(__name__)

_PROMPT = """\
Sos un extractor de datos para una agencia de turismo. Analizá esta foto de un tiquete de venta
y extraé todos los campos que puedas leer. Respondé SOLO con JSON válido con estos campos:

{
  "numero_ticket": null,
  "nombre_cliente": null,
  "telefono": null,
  "cliente_hotel": null,
  "numero_habitacion": null,
  "destinos": [],
  "fecha_salida": null,
  "adultos": null,
  "ninos": null,
  "valor": null,
  "abono": null,
  "vendedor": null,
  "confianza": 0.0
}

Reglas:
- numero_ticket: entero o null
- destinos: lista de strings con los destinos marcados
- fecha_salida: string en formato "DD/MM/YYYY" o null (solo la fecha, sin hora)
- adultos, ninos: enteros o null
- valor, abono: números decimales (pesos colombianos) o null
- confianza: float 0.0-1.0 (qué tan bien se pudo leer la imagen)
- Si no podés leer un campo con certeza, usá null
- No incluyas texto fuera del JSON\
"""

_DATE_FORMATS = [
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
]


class ExtractorClaude(ExtractorIA):
    """ExtractorIA adapter that calls the Anthropic Claude vision API."""

    def __init__(
        self,
        api_key: str,
        modelo: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self._api_key = api_key
        self._modelo = modelo

    def extraer_de_foto(self, ruta_foto: str) -> DatosExtraidos:
        with open(ruta_foto, "rb") as f:
            imagen_b64 = base64.b64encode(f.read()).decode("ascii")

        client = anthropic.Anthropic(api_key=self._api_key)
        response = client.messages.create(
            model=self._modelo,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": imagen_b64,
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )

        block = response.content[0]
        if not isinstance(block, TextBlock):
            _logger.warning("Claude returned unexpected block type: %s", type(block).__name__)
            return DatosExtraidos(confianza=Decimal("0"))
        raw: str = block.text
        _logger.info("Claude raw response: %s", raw[:500])
        return self._parsear_respuesta(raw)

    def _parsear_respuesta(self, raw: str) -> DatosExtraidos:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return DatosExtraidos(confianza=Decimal("0"))

        try:
            valor_venta: Dinero | None = None
            if data.get("valor") is not None:
                valor_venta = Dinero(Decimal(str(data["valor"])))

            abono: Dinero | None = None
            if data.get("abono") is not None:
                abono = Dinero(Decimal(str(data["abono"])))

            destinos_raw = data.get("destinos")
            destinos: tuple[str, ...] = (
                tuple(str(d) for d in destinos_raw) if isinstance(destinos_raw, list) else ()
            )

            fecha_salida: datetime.datetime | None = None
            fecha_str = data.get("fecha_salida")
            if fecha_str:
                for fmt in _DATE_FORMATS:
                    try:
                        fecha_salida = datetime.datetime.strptime(str(fecha_str), fmt)
                        break
                    except ValueError:
                        continue

            raw_conf = data.get("confianza", 0.0)
            confianza = Decimal(str(raw_conf))
            confianza = max(Decimal("0"), min(Decimal("1"), confianza))

            def _int_or_none(key: str) -> int | None:
                val = data.get(key)
                return int(val) if val is not None else None

            return DatosExtraidos(
                valor_venta=valor_venta,
                abono=abono,
                nombre_cliente=data.get("nombre_cliente"),
                telefono=data.get("telefono"),
                cliente_hotel=data.get("cliente_hotel"),
                numero_habitacion=data.get("numero_habitacion"),
                servicio_nombre=data.get("vendedor"),
                destinos=destinos,
                fecha_salida=fecha_salida,
                adultos=_int_or_none("adultos"),
                ninos=_int_or_none("ninos"),
                numero_ticket=_int_or_none("numero_ticket"),
                confianza=confianza,
            )
        except (InvalidOperation, ValueError, TypeError):
            return DatosExtraidos(confianza=Decimal("0"))
