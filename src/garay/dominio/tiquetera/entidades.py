from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from garay.dominio.tiquetera.errores import FotoReferenciaVacia, TiqueteraYaProcesada
from garay.dominio.tiquetera.valor_objetos import DatosExtraidos


@dataclass(eq=False)
class Tiquetera:
    id: uuid.UUID
    venta_id: uuid.UUID
    foto_referencia: str
    numero_fisico: int | None = None  # papel fisico, ingresado por el usuario
    numero_ticket: int | None = None  # asignado por DB (Sequence), None antes de persistir
    procesada: bool = field(default=False)
    datos_extraidos: DatosExtraidos | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.foto_referencia.strip():
            raise FotoReferenciaVacia("La foto de referencia no puede estar vacia.")

    def marcar_procesada(self, datos: DatosExtraidos) -> None:
        if self.procesada:
            raise TiqueteraYaProcesada("La tiquetera ya fue procesada.")
        self.procesada = True
        self.datos_extraidos = datos

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Tiquetera) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
