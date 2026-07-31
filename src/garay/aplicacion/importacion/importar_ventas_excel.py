"""Importa las ventas historicas de la planilla de contabilidad al modelo de dominio.

Escribe cada fila (ya deduplicada por el lector) como una `Venta` + su
`ComisionRegistrada`, resolviendo los FKs (cliente, servicio via alias, punto de
venta). NO reusa `RegistrarVentaService`: la comision se SNAPSHOTEA de la planilla
(no se recalcula), no notifica, y usa `uuid5` determinista para ser idempotente.

Hebert (el 20% del dueno del restaurante en Crespo) queda como la comision del
punto de venta: `punto = margen - agencia - vendedor - cerrador` (residual). En
Hotel/Externas ese residual es ~0.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from garay.aplicacion.importacion.errores import DescripcionSinMapeo
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import EstadoVenta, TipoCliente
from garay.dominio.puertos.repositorios import (
    ClienteRepository,
    ComisionRegistradaRepository,
    PuntoDeVentaRepository,
    ServicioRepository,
    VentaRepository,
)
from garay.dominio.puertos.servicios_externos import FilaVentaImportada, LectorVentasExcel
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

_NS = uuid.UUID("f0e1d2c3-b4a5-6789-abcd-ef0123456789")
_CERO = Dinero(0)
_CANAL_HOTEL = "Hotel"
_CANAL_CRESPO = "Crespo"


@dataclass(frozen=True)
class ResultadoImportacion:
    ventas_creadas: int
    clientes_creados: int
    ventas_omitidas: int
    total_valor: Dinero
    total_agencia: Dinero


def _norm_desc(descripcion: str) -> str:
    return " ".join(descripcion.strip().lower().split())


def _tipo_cliente(canal: str) -> TipoCliente:
    return TipoCliente.INTERNO if canal == _CANAL_HOTEL else TipoCliente.EXTERNO


class ImportarVentasExcelService:
    def __init__(
        self,
        lector: LectorVentasExcel,
        ventas: VentaRepository,
        clientes: ClienteRepository,
        servicios: ServicioRepository,
        puntos: PuntoDeVentaRepository,
        comisiones: ComisionRegistradaRepository,
        alias: dict[str, int],
    ) -> None:
        self._lector = lector
        self._ventas = ventas
        self._clientes = clientes
        self._servicios = servicios
        self._puntos = puntos
        self._comisiones = comisiones
        self._alias = alias

    def ejecutar(self, ruta: str, mes: int, anio: int) -> ResultadoImportacion:
        filas = [
            f
            for f in self._lector.leer(ruta)
            if f.fecha.month == mes and f.fecha.year == anio
        ]
        servicios_por_numero = {s.numero: s for s in self._servicios.listar()}
        punto_crespo = self._puntos.buscar_por_nombre(_CANAL_CRESPO)
        punto_crespo_id = punto_crespo.id if punto_crespo is not None else None

        clientes_creados = 0
        omitidas = 0
        total_valor = _CERO
        total_agencia = _CERO
        for f in filas:
            if f.valor <= _CERO or f.neto > f.valor:
                omitidas += 1
                continue
            servicio_id = self._resolver_servicio(f.descripcion, servicios_por_numero)
            cliente_id, creado = self._resolver_cliente(f)
            if creado:
                clientes_creados += 1
            punto_id = punto_crespo_id if f.canal == _CANAL_CRESPO else None

            venta = Venta(
                id=self._venta_id(f),
                valor_venta=f.valor,
                neto=f.neto,
                servicio_ids=[servicio_id],
                cliente_id=cliente_id,
                tipo_cliente=_tipo_cliente(f.canal),
                fecha=f.fecha,
                participantes=Participantes(
                    vendedor_nombre=f.vendedor_nombre,
                    cerrador_nombre=f.cerrador_nombre,
                    punto_de_venta_id=punto_id,
                    referido_nombre=None,
                ),
                estado=EstadoVenta.PROCESADA,
                canal_origen=f.canal,
            )
            self._ventas.guardar(venta)
            self._comisiones.guardar(
                ComisionRegistrada(venta_id=venta.id, desglose=self._desglose(f), fecha=f.fecha)
            )
            total_valor = total_valor + f.valor
            total_agencia = total_agencia + f.agencia

        return ResultadoImportacion(
            ventas_creadas=len(filas) - omitidas,
            clientes_creados=clientes_creados,
            ventas_omitidas=omitidas,
            total_valor=total_valor,
            total_agencia=total_agencia,
        )

    def _resolver_servicio(
        self, descripcion: str, servicios_por_numero: dict[int, Servicio]
    ) -> uuid.UUID:
        numero = self._alias.get(_norm_desc(descripcion))
        servicio = servicios_por_numero.get(numero) if numero is not None else None
        if servicio is None:
            raise DescripcionSinMapeo(f"Sin servicio para la descripcion: {descripcion!r}")
        return servicio.id

    def _resolver_cliente(self, f: FilaVentaImportada) -> tuple[uuid.UUID, bool]:
        existente = self._clientes.buscar_por_nombre(f.cliente_nombre)
        if existente is not None:
            return existente.id, False
        cliente = Cliente(
            id=uuid.uuid5(_NS, f"cliente:{f.cliente_nombre.lower()}"),
            nombre=f.cliente_nombre,
            tipo=_tipo_cliente(f.canal),
        )
        self._clientes.guardar(cliente)
        return cliente.id, True

    def _venta_id(self, f: FilaVentaImportada) -> uuid.UUID:
        clave = (
            f"{f.cliente_nombre.lower()}|{f.fecha.isoformat()}"
            f"|{int(f.valor.monto)}|{f.descripcion.lower()[:15]}"
        )
        return uuid.uuid5(_NS, clave)

    def _desglose(self, f: FilaVentaImportada) -> DesgloseComision:
        punto = f.margen - f.agencia - f.comision_vendedor - f.comision_cerrador
        margen = f.margen.monto

        def pct(x: Dinero) -> Decimal:
            return x.monto / margen if margen else Decimal("0")

        snapshot = SnapshotReglas(
            tipo_cliente=_tipo_cliente(f.canal),
            porcentaje_vendedor=pct(f.comision_vendedor),
            porcentaje_cerrador=pct(f.comision_cerrador),
            porcentaje_referido_maximo=Decimal("0"),
            porcentaje_capa_punto=pct(punto),
        )
        return DesgloseComision(
            vendedor=f.comision_vendedor,
            cerrador=f.comision_cerrador,
            punto_de_venta=punto,
            referido=_CERO,
            agencia=f.agencia,
            snapshot=snapshot,
        )
