from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass

from garay.dominio.comun.dinero import Dinero
from garay.dominio.tiquetera.valor_objetos import DatosExtraidos
from garay.dominio.ventas.contexto import ContextoVenta


@dataclass(frozen=True)
class FilaVentaImportada:
    """Una fila cruda de venta leida de la hoja de contabilidad, ya deduplicada.

    Representa lo que dice la planilla, antes de resolver FKs (cliente, servicio,
    punto de venta). El canal es el eje de venta (Hotel / Externas / Crespo).
    """

    canal: str
    cliente_nombre: str
    fecha: datetime.date
    descripcion: str
    valor: Dinero
    neto: Dinero
    margen: Dinero
    agencia: Dinero
    vendedor_nombre: str | None
    cerrador_nombre: str | None


class LectorVentasExcel(ABC):
    @abstractmethod
    def leer(self, ruta: str) -> list[FilaVentaImportada]:
        """Lee y deduplica las ventas de la planilla de contabilidad."""
        ...


class ExtractorIA(ABC):
    @abstractmethod
    def extraer_de_foto(self, ruta_foto: str) -> DatosExtraidos: ...


class NotificadorGrupo(ABC):
    @abstractmethod
    def notificar(self, mensaje: str, grupo_id: str) -> None: ...


class ExtractorReserva(ABC):
    @abstractmethod
    def extraer_de_foto(self, foto_bytes: bytes) -> ContextoVenta: ...


class NotificadorEmail(ABC):
    @abstractmethod
    def enviar(self, destinatario: str, asunto: str, cuerpo_html: str) -> None: ...
