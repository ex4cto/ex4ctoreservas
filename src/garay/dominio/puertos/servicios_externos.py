from __future__ import annotations

from abc import ABC, abstractmethod

from garay.dominio.tiquetera.valor_objetos import DatosExtraidos
from garay.dominio.ventas.contexto import ContextoVenta


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
