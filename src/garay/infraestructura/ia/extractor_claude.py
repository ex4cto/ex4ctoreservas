"""Concrete adapter: ExtractorIA backed by the Anthropic Claude vision API."""

from __future__ import annotations

import base64
import datetime
import json
import logging
import re
from decimal import Decimal, InvalidOperation

import anthropic
from anthropic.types import TextBlock

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.servicios_externos import ExtractorIA
from garay.dominio.tiquetera.valor_objetos import DatosExtraidos

_logger = logging.getLogger(__name__)

_PROMPT = """\
Sos un extractor de datos de tiquetes de la agencia Garay Tours (Cartagena, Colombia).
Analizá la foto y extraé los campos según el layout exacto que se describe abajo.
Respondé ÚNICAMENTE con JSON válido, sin texto adicional ni bloques de código.

── LAYOUT DEL TIQUETE PROMO ──────────────────────────────────────
CAMPO N° (serial del tiquete): recuadro gris en el borde derecho del
tiquete, etiquetado "N°". Puede ser numérico (ej: 0845) o alfanumérico
(ej: C047). Este campo es el número de serie del papel impreso, NO dinero.
→ va en "numero_ticket" (string).

FILA 1: Nombre: [nombre cliente]  |  Niños: [entero]  |  Adultos: [entero]
FILA 2: Fecha y hora de salida: [DD/MM/YYYY HH:MM]  |  Hotel: [nombre hotel]
FILA 3: N° Habitación: [número]  |  Tel: [teléfono]  |  Vendedor: [nombre]

FILA DE DINERO (tres campos en línea, de izquierda a derecha):
  Valor:  [precio total de venta en COP, ej: 260000]
  Abono:  [anticipo pagado por el cliente en COP, ej: 130000]
            Si dice "OK" en lugar de número → null
  Saldo:  [Valor - Abono, campo calculado — NO incluir en JSON]

CUADRÍCULA DE CHECKBOXES:
  Playa blanca | Islas de Rosario | Playa tranquila | Cholen | Playa linda
  4 Islas | 5 Islas | Palmerito Beach | Punta Arena | Rumba en Chiva
  Tours Bahia | Playa Cristal Full Day | Playa Cristal | Barú + Mapache + Snorkel
  Otros → Cual: [texto libre]
  Incluir en "destinos" SOLO los que tengan una X visible.

── REGLAS CRÍTICAS ───────────────────────────────────────────────
- "numero_ticket": extraé el valor del campo N° como string. NUNCA uses
  un monto monetario como numero_ticket.
- "abono": el monto junto a "Abono:" en la fila de dinero. NUNCA uses el
  valor del campo N° como abono.
- "destinos": lista solo los checkboxes marcados con X. Si ninguno → [].
- "fecha_salida": formato "DD/MM/YYYY HH:MM" o "DD/MM/YYYY". Si incluye
  AM/PM, convertí a 24h. Solo fecha/hora de salida.
- Si no podés leer un campo con certeza → null.
──────────────────────────────────────────────────────────────────

{
  "numero_ticket": null,
  "nombre_cliente": null,
  "telefono": null,
  "cliente_hotel": null,
  "numero_habitacion": null,
  "vendedor": null,
  "destinos": [],
  "fecha_salida": null,
  "adultos": null,
  "ninos": null,
  "valor": null,
  "abono": null,
  "confianza": 0.0
}\
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
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return DatosExtraidos(confianza=Decimal("0"))
        json_str = match.group()
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Claude sometimes writes leading zeros in numbers (e.g. 0845) which are
            # invalid JSON. Strip them and retry once.
            fixed = re.sub(r"([:,\[]\s*)0+(\d)", r"\1\2", json_str)
            try:
                data = json.loads(fixed)
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
                numero_ticket=(
                    str(data["numero_ticket"])
                    if data.get("numero_ticket") is not None
                    else None
                ),
                confianza=confianza,
            )
        except (InvalidOperation, ValueError, TypeError):
            return DatosExtraidos(confianza=Decimal("0"))
