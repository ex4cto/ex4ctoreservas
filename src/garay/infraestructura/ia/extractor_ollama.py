"""Concrete adapter: ExtractorIA backed by Ollama (llava model)."""

from __future__ import annotations

import base64
import datetime
import json
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.servicios_externos import ExtractorIA
from garay.dominio.tiquetera.valor_objetos import DatosExtraidos
from garay.infraestructura.ia.errores import ModeloNoEncontrado, OllamaNoDisponible

_PROMPT = """\
Sos un extractor de datos para una agencia de turismo. Analizá esta foto de un tiquete de venta
y extraé todos los campos que puedas leer. Respondé SOLO con JSON con estos campos:

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
- fecha_salida: "DD/MM/YYYY HH:MM" o null
- adultos, ninos: enteros o null
- valor, abono: números decimales (pesos colombianos) o null
- confianza: float 0.0-1.0 (qué tan bien se pudo leer la imagen)
- Si no podés leer un campo con certeza, usá null\
"""

_DATE_FORMATS = [
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
]


class ExtractorOllama(ExtractorIA):
    """ExtractorIA adapter that calls a local Ollama instance with the llava model."""

    def __init__(
        self,
        url: str = "http://localhost:11434",
        modelo: str = "llava",
        timeout: int = 60,
    ) -> None:
        self._url = url.rstrip("/")
        self._modelo = modelo
        self._timeout = timeout

    def extraer_de_foto(self, ruta_foto: str) -> DatosExtraidos:
        with open(ruta_foto, "rb") as f:
            imagen_b64 = base64.b64encode(f.read()).decode("ascii")

        payload = json.dumps(
            {
                "model": self._modelo,
                "prompt": _PROMPT,
                "images": [imagen_b64],
                "stream": False,
                "format": "json",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self._url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = resp.read()
        except ConnectionRefusedError as exc:
            raise OllamaNoDisponible("Ollama server is not reachable") from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ModeloNoEncontrado(
                    f"Model '{self._modelo}' not found in Ollama"
                ) from exc
            raise OllamaNoDisponible(f"HTTP error from Ollama: {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise OllamaNoDisponible("Could not connect to Ollama") from exc

        try:
            envelope = json.loads(body)
            raw: str = envelope["response"]
        except (json.JSONDecodeError, KeyError):
            return DatosExtraidos(confianza=Decimal("0"))

        return self._parsear_respuesta(raw)

    def _parsear_respuesta(self, raw: str) -> DatosExtraidos:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return DatosExtraidos(confianza=Decimal("0"))

        try:
            # Financial
            valor_venta: Dinero | None = None
            if data.get("valor") is not None:
                valor_venta = Dinero(Decimal(str(data["valor"])))

            abono: Dinero | None = None
            if data.get("abono") is not None:
                abono = Dinero(Decimal(str(data["abono"])))

            # Destinos
            destinos_raw = data.get("destinos")
            destinos: tuple[str, ...] = (
                tuple(str(d) for d in destinos_raw)
                if isinstance(destinos_raw, list)
                else ()
            )

            # Fecha
            fecha_salida: datetime.datetime | None = None
            fecha_str = data.get("fecha_salida")
            if fecha_str:
                for fmt in _DATE_FORMATS:
                    try:
                        fecha_salida = datetime.datetime.strptime(str(fecha_str), fmt)
                        break
                    except ValueError:
                        continue

            # Confianza — clamped to [0, 1]
            raw_conf = data.get("confianza", 0.0)
            confianza = Decimal(str(raw_conf))
            if confianza < Decimal("0"):
                confianza = Decimal("0")
            if confianza > Decimal("1"):
                confianza = Decimal("1")

            # Integers
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
