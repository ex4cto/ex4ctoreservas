"""ContextoVenta — shared VO for the conversation FSM and extraction ports."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from garay.dominio.comun.tipos import TipoCliente


@dataclass
class ContextoVenta:
    tipo_cliente: TipoCliente | None = None
    punto_de_venta_nombre: str | None = None
    destinos_numeros: list[int] = field(default_factory=list)
    destinos_nombres: list[str] = field(default_factory=list)
    familia_seleccionada: str | None = None
    cliente_nombre: str | None = None
    cliente_telefono: str | None = None
    cliente_hotel: str | None = None
    cliente_habitacion: str | None = None
    sin_hotel: bool = False
    fecha_salida: datetime.datetime | None = None
    adultos: int | None = None
    ninos: int | None = None
    valor: Decimal | None = None
    abono: Decimal | None = None
    neto: Decimal | None = None
    vendedor_nombre: str | None = None
    cerrador_nombre: str | None = None
    referido_nombre: str | None = None
    vendedor_id: uuid.UUID | None = None
    cerrador_id: uuid.UUID | None = None
    numero_fisico: str | None = None
    rol_registrante: str | None = None  # "vendedor" | "cerrador" | "ambos"
    modo_edicion: bool = False
    tour_adicional: bool = False
    foto_modo: bool = False
    cliente_email: str | None = None
    cliente_identificacion: str | None = None
    cliente_tipo_identificacion: str | None = None
    canal_origen: str | None = None
    fechas_por_servicio: dict[int, datetime.datetime] = field(default_factory=dict)
    horarios_por_servicio: dict[int, str] = field(default_factory=dict)
