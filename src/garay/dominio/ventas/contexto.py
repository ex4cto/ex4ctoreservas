"""ContextoVenta — shared VO for the conversation FSM and extraction ports."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from garay.dominio.comun.tipos import TipoCliente


@dataclass
class ContextoVenta:
    tipo_cliente: TipoCliente | None = None
    punto_de_venta_nombre: str | None = None
    destinos_numeros: list[int] = field(default_factory=list)
    destinos_nombres: list[str] = field(default_factory=list)
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
    numero_fisico: str | None = None
    rol_registrante: str | None = None  # "vendedor" | "cerrador" | "ambos"
    modo_edicion: bool = False
    foto_modo: bool = False
    cliente_email: str | None = None
    cliente_identificacion: str | None = None
    cliente_tipo_identificacion: str | None = None
    canal_origen: str | None = None
