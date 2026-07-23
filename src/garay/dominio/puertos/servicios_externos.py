from __future__ import annotations

from abc import ABC, abstractmethod

from garay.dominio.tiquetera.valor_objetos import DatosExtraidos


class ExtractorIA(ABC):
    @abstractmethod
    def extraer_de_foto(self, ruta_foto: str) -> DatosExtraidos: ...


class NotificadorGrupo(ABC):
    @abstractmethod
    def notificar(self, mensaje: str, grupo_id: str) -> None: ...
