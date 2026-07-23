"""Logging estructurado en JSON, sin dependencias externas."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class FormateadorJson(logging.Formatter):
    """Formatea cada registro como una linea JSON estructurada."""

    def format(self, record: logging.LogRecord) -> str:
        datos: dict[str, str] = {
            "ts": datetime.now(UTC).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        if record.exc_info:
            datos["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False)


def configurar_logging(nivel: int = logging.INFO) -> None:
    """Configura el logger raiz con salida JSON a stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormateadorJson())

    raiz = logging.getLogger()
    raiz.handlers.clear()
    raiz.addHandler(handler)
    raiz.setLevel(nivel)
