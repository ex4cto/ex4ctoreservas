"""ConsultaVentasService — flattened, FK-resolved sales rows for the dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ClienteRepository,
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
    ) -> None:
        self._ventas = ventas
        self._clientes = clientes
        self._servicios = servicios

    def ejecutar(self, desde: date, hasta: date) -> list[FilaVentaConsulta]:
        ventas = self._ventas.listar_por_periodo(desde, hasta)
        if not ventas:
            return []

        nombre_por_cliente = {c.id: c.nombre for c in self._clientes.listar()}
        nombre_por_servicio = {s.id: s.nombre for s in self._servicios.listar()}

        filas: list[FilaVentaConsulta] = []
        for v in ventas:
            servicios_txt = ", ".join(
                nombre_por_servicio[sid]
                for sid in v.servicio_ids
                if sid in nombre_por_servicio
            )
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
                    vendedor=v.participantes.vendedor_nombre,
                    cerrador=v.participantes.cerrador_nombre,
                )
            )
        return filas
