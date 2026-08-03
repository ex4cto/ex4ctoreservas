"""ConsultaVentasService — flattened, FK-resolved sales rows for the dashboard."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ClienteRepository,
    FreelancerRepository,
    ServicioRepository,
    VentaRepository,
)


@dataclass(frozen=True)
class FilaVentaConsulta:
    fecha: date
    cliente_nombre: str
    servicios: str
    valor: Dinero
    neto: Dinero
    ganancia: Dinero
    tipo_cliente: str
    adultos: int
    ninos: int
    estado: str
    canal_origen: str | None = None
    vendedor: str | None = None
    cerrador: str | None = None


class ConsultaVentasService:
    def __init__(
        self,
        ventas: VentaRepository,
        clientes: ClienteRepository,
        servicios: ServicioRepository,
        freelancers: FreelancerRepository,
    ) -> None:
        self._ventas = ventas
        self._clientes = clientes
        self._servicios = servicios
        self._freelancers = freelancers

    def ejecutar(self, desde: date, hasta: date) -> list[FilaVentaConsulta]:
        ventas = self._ventas.listar_por_periodo(desde, hasta)
        if not ventas:
            return []

        nombre_por_cliente = {c.id: c.nombre for c in self._clientes.listar()}
        nombre_por_servicio = {s.id: s.nombre for s in self._servicios.listar()}

        # Build display dict once — includes inactive freelancers
        display_por_id: dict[uuid.UUID, str] = {
            f.id: (f.display or f.nombre) for f in self._freelancers.listar_todos()
        }

        filas: list[FilaVentaConsulta] = []
        for v in ventas:
            servicios_txt = ", ".join(
                nombre_por_servicio[sid]
                for sid in v.servicio_ids
                if sid in nombre_por_servicio
            )

            p = v.participantes

            # Two-level resolution: id → display, None-id → snapshot
            if p.vendedor_id is not None:
                vendedor = display_por_id.get(p.vendedor_id, p.vendedor_nombre)
            else:
                vendedor = p.vendedor_nombre

            if p.cerrador_id is not None:
                cerrador = display_por_id.get(p.cerrador_id, p.cerrador_nombre)
            else:
                cerrador = p.cerrador_nombre

            filas.append(
                FilaVentaConsulta(
                    fecha=v.fecha,
                    cliente_nombre=nombre_por_cliente.get(v.cliente_id, "—"),
                    servicios=servicios_txt,
                    valor=v.valor_venta,
                    neto=v.neto,
                    ganancia=v.ganancia,
                    tipo_cliente=str(v.tipo_cliente),
                    adultos=v.adultos,
                    ninos=v.ninos,
                    estado=str(v.estado),
                    canal_origen=v.canal_origen,
                    vendedor=vendedor,
                    cerrador=cerrador,
                )
            )
        return filas
