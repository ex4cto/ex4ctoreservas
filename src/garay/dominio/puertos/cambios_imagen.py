"""Port definitions for pending catalog image changes."""

from __future__ import annotations

import dataclasses
import datetime
from abc import ABC, abstractmethod


@dataclasses.dataclass(frozen=True)
class CambioPendiente:
    """A single pending catalog change record."""

    id: int
    descripcion: str
    creado_en: datetime.datetime


class CambiosPendientesRepository(ABC):
    """Port: persistence for catalog change records."""

    @abstractmethod
    def registrar(self, descripcion: str) -> None:
        """Insert a new pending change."""
        ...

    @abstractmethod
    def listar_todos(self) -> list[CambioPendiente]:
        """Return all pending changes ordered by creation time ASC."""
        ...

    @abstractmethod
    def limpiar(self) -> None:
        """Delete all pending change records."""
        ...
