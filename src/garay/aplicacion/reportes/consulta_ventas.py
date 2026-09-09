"""ConsultaVentasService — flattened, FK-resolved sales rows for the dashboard."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ClienteRepository,
    ComisionRegistradaRepository,
    FacturaRepository,
    FreelancerRepository,
    PuntoDeVentaRepository,
    ServicioRepository,
    VentaRepository,
)
from garay.dominio.ventas.entidades import Venta


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
    # --- Raw-data expansion (PR A) ---
    venta_id: str = ""
    abono: Dinero | None = None
    saldo_pendiente: Dinero | None = None
    anulada: bool = False
    factura_idioma: str = "es"
    cliente_telefono: str | None = None
    cliente_email: str | None = None
    cliente_identificacion: str | None = None
    cliente_hotel: str | None = None
    cliente_habitacion: str | None = None
    punto_de_venta: str | None = None
    referido: str | None = None
    fechas_horarios: str = ""
    # --- Comisión + factura (PR B) ---
    comision_vendedor: Dinero | None = None
    comision_cerrador: Dinero | None = None
    comision_punto_de_venta: Dinero | None = None
    comision_referido: Dinero | None = None
    comision_agencia: Dinero | None = None
    factura_numero: str | None = None
    factura_estado: str | None = None


def _detalle_tours(venta: Venta, nombre_por_servicio: dict[uuid.UUID, str]) -> str:
    """Per-service schedule: 'Tour — DD/MM/YYYY HH:MM (horario)' joined by '; '.

    Falls back to the venta's primary fecha when a service has no per-service date.
    """
    partes: list[str] = []
    for sid in venta.servicio_ids:
        nombre = nombre_por_servicio.get(sid, str(sid))
        fecha_serv = (venta.fechas_por_servicio or {}).get(sid)
        if fecha_serv is not None:
            fecha_txt = fecha_serv.strftime("%d/%m/%Y %H:%M")
        else:
            fecha_txt = venta.fecha.strftime("%d/%m/%Y")
        horario = (venta.horarios_por_servicio or {}).get(sid)
        detalle = f"{nombre} — {fecha_txt}"
        if horario:
            detalle += f" ({horario})"
        partes.append(detalle)
    return "; ".join(partes)


class ConsultaVentasService:
    def __init__(
        self,
        ventas: VentaRepository,
        clientes: ClienteRepository,
        servicios: ServicioRepository,
        freelancers: FreelancerRepository,
        puntos_de_venta: PuntoDeVentaRepository,
        comisiones: ComisionRegistradaRepository,
        facturas: FacturaRepository,
    ) -> None:
        self._ventas = ventas
        self._clientes = clientes
        self._servicios = servicios
        self._freelancers = freelancers
        self._puntos = puntos_de_venta
        self._comisiones = comisiones
        self._facturas = facturas

    def ejecutar(self, desde: date, hasta: date) -> list[FilaVentaConsulta]:
        ventas = self._ventas.listar_por_periodo(desde, hasta)
        if not ventas:
            return []

        cliente_por_id = {c.id: c for c in self._clientes.listar()}
        nombre_por_servicio = {s.id: s.nombre for s in self._servicios.listar()}
        punto_por_id = {p.id: p.nombre for p in self._puntos.listar()}

        # Bulk-load commission + invoice indexed by venta_id (one query each)
        venta_ids = [v.id for v in ventas]
        comision_por_venta = {
            c.venta_id: c for c in self._comisiones.listar_por_venta_ids(venta_ids)
        }
        factura_por_venta = {
            f.venta_id: f for f in self._facturas.listar_por_venta_ids(venta_ids)
        }

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

            cliente = cliente_por_id.get(v.cliente_id)
            saldo = v.valor_venta - v.abono if v.abono is not None else v.valor_venta
            punto = (
                punto_por_id.get(p.punto_de_venta_id)
                if p.punto_de_venta_id is not None
                else None
            )

            comision = comision_por_venta.get(v.id)
            desglose = comision.desglose if comision is not None else None
            factura = factura_por_venta.get(v.id)

            filas.append(
                FilaVentaConsulta(
                    fecha=v.fecha,
                    cliente_nombre=cliente.nombre if cliente is not None else "—",
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
                    venta_id=str(v.id),
                    abono=v.abono,
                    saldo_pendiente=saldo,
                    anulada=v.anulada,
                    factura_idioma=v.factura_idioma,
                    cliente_telefono=cliente.telefono if cliente is not None else None,
                    cliente_email=cliente.email if cliente is not None else None,
                    cliente_identificacion=(
                        cliente.identificacion if cliente is not None else None
                    ),
                    cliente_hotel=cliente.hotel if cliente is not None else None,
                    cliente_habitacion=(
                        cliente.numero_habitacion if cliente is not None else None
                    ),
                    punto_de_venta=punto,
                    referido=p.referido_nombre,
                    fechas_horarios=_detalle_tours(v, nombre_por_servicio),
                    comision_vendedor=desglose.vendedor if desglose else None,
                    comision_cerrador=desglose.cerrador if desglose else None,
                    comision_punto_de_venta=(
                        desglose.punto_de_venta if desglose else None
                    ),
                    comision_referido=desglose.referido if desglose else None,
                    comision_agencia=desglose.agencia if desglose else None,
                    factura_numero=factura.numero if factura is not None else None,
                    factura_estado=(
                        str(factura.estado_envio) if factura is not None else None
                    ),
                )
            )
        return filas
