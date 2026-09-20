"""SplitSociosService — calculates the historical revenue split for all partners."""

from __future__ import annotations

import datetime

from garay.aplicacion.socios.split import (
    ResumenFreelancerPeriodo,
    ResumenSocio,
    ResumenSocioPeriodo,
    ResumenSplitPeriodo,
    ResumenSplitSocios,
    ResumenVentaDetalle,
)
from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ComisionRegistradaRepository,
    PagoSocioRepository,
    SocioConfigRepository,
    VentaRepository,
)
from garay.dominio.socios.servicio import calcular_split_venta


class SplitSociosService:
    def __init__(
        self,
        ventas: VentaRepository,
        comisiones: ComisionRegistradaRepository,
        socios_config: SocioConfigRepository,
        pagos_socio: PagoSocioRepository,
    ) -> None:
        self._ventas = ventas
        self._comisiones = comisiones
        self._socios_config = socios_config
        self._pagos_socio = pagos_socio

    def calcular_acumulado(
        self, desde: datetime.date | None = None
    ) -> ResumenSplitSocios:
        """Calculate the split across all non-annulled sales, optionally from *desde*."""
        if desde is not None:
            ventas = self._ventas.listar_por_periodo(desde, datetime.date.today())
        else:
            ventas = self._ventas.listar()
        configs = self._socios_config.listar()

        venta_ids = [v.id for v in ventas]
        comisiones = self._comisiones.listar_por_venta_ids(venta_ids) if venta_ids else []

        total_agencia = sum(
            (c.desglose.agencia for c in comisiones), start=Dinero(0)
        )

        # If no partners configured, return empty split with the total_agencia
        if not configs:
            return ResumenSplitSocios(por_socio=(), total_agencia=total_agencia)

        acumulado_por_socio = calcular_split_venta(total_agencia, configs)

        pagos = self._pagos_socio.listar()
        pagado_por_socio: dict[str, Dinero] = {}
        for pago in pagos:
            nombre = pago.nombre_socio
            pagado_por_socio[nombre] = pagado_por_socio.get(nombre, Dinero(0)) + pago.monto

        resumenes: list[ResumenSocio] = []
        for config in configs:
            nombre = config.nombre
            acumulado = acumulado_por_socio.get(nombre, Dinero(0))
            pagado = pagado_por_socio.get(nombre, Dinero(0))
            pendiente = acumulado - pagado
            resumenes.append(
                ResumenSocio(
                    nombre=nombre,
                    porcentaje=config.porcentaje,
                    acumulado=acumulado,
                    pagado=pagado,
                    pendiente=pendiente,
                )
            )

        return ResumenSplitSocios(
            por_socio=tuple(resumenes),
            total_agencia=total_agencia,
        )

    def calcular_periodo(
        self, desde: datetime.date, hasta: datetime.date
    ) -> ResumenSplitPeriodo:
        """Calculate the split for sales in [desde, hasta] (both bounds inclusive).

        Does NOT access PagoSocioRepository — there is no date-filtered payment
        query, and this view has no 'pendiente' concept.
        """
        ventas = self._ventas.listar_por_periodo(desde, hasta)
        configs = self._socios_config.listar()

        venta_ids = [v.id for v in ventas]
        comisiones = self._comisiones.listar_por_venta_ids(venta_ids) if venta_ids else []

        # Build lookup: venta_id → ComisionRegistrada
        comision_por_venta_id = {c.venta_id: c for c in comisiones}

        total_agencia = sum(
            (c.desglose.agencia for c in comisiones), start=Dinero(0)
        )
        total_bruto = sum(
            (v.valor_venta for v in ventas), start=Dinero(0)
        )
        total_comisiones_freelancer = sum(
            (
                c.desglose.vendedor + c.desglose.cerrador + c.desglose.punto_de_venta
                for c in comisiones
            ),
            start=Dinero(0),
        )
        ventas_count = len(ventas)

        # Build per-sale detail and per-freelancer aggregation
        freelancer_totales: dict[str, Dinero] = {}
        ventas_detalle_list: list[ResumenVentaDetalle] = []

        for venta in ventas:
            com = comision_por_venta_id.get(venta.id)
            if com is not None:
                dv = com.desglose.vendedor
                dc = com.desglose.cerrador
                dp = com.desglose.punto_de_venta
                da = com.desglose.agencia
            else:
                dv = dc = dp = da = Dinero(0)

            # Per-sale split
            per_sale_agencia = da
            if configs:
                per_sale_split_map = calcular_split_venta(per_sale_agencia, configs)
                sale_socios = tuple(
                    ResumenSocioPeriodo(
                        nombre=c.nombre,
                        porcentaje=c.porcentaje,
                        acumulado=per_sale_split_map.get(c.nombre, Dinero(0)),
                    )
                    for c in configs
                )
            else:
                sale_socios = ()

            ventas_detalle_list.append(
                ResumenVentaDetalle(
                    venta_id=venta.id,
                    fecha=venta.fecha,
                    vendedor_nombre=venta.participantes.vendedor_nombre,
                    cerrador_nombre=venta.participantes.cerrador_nombre,
                    valor_bruto=venta.valor_venta,
                    desglose_vendedor=dv,
                    desglose_cerrador=dc,
                    desglose_punto=dp,
                    desglose_agencia=da,
                    split_socios=sale_socios,
                )
            )

            # Freelancer aggregation
            vendedor_nombre = venta.participantes.vendedor_nombre
            if vendedor_nombre is not None and dv > Dinero(0):
                freelancer_totales[vendedor_nombre] = (
                    freelancer_totales.get(vendedor_nombre, Dinero(0)) + dv
                )
            cerrador_nombre = venta.participantes.cerrador_nombre
            if cerrador_nombre is not None and dc > Dinero(0):
                freelancer_totales[cerrador_nombre] = (
                    freelancer_totales.get(cerrador_nombre, Dinero(0)) + dc
                )

        por_freelancer = tuple(
            ResumenFreelancerPeriodo(nombre=nombre, comision=monto)
            for nombre, monto in freelancer_totales.items()
        )

        if not configs:
            return ResumenSplitPeriodo(
                por_socio=(),
                total_agencia=total_agencia,
                total_bruto=total_bruto,
                total_comisiones_freelancer=total_comisiones_freelancer,
                ventas_count=ventas_count,
                ventas_detalle=tuple(ventas_detalle_list),
                por_freelancer=por_freelancer,
            )

        acumulado_por_socio = calcular_split_venta(total_agencia, configs)

        resumenes: list[ResumenSocioPeriodo] = [
            ResumenSocioPeriodo(
                nombre=config.nombre,
                porcentaje=config.porcentaje,
                acumulado=acumulado_por_socio.get(config.nombre, Dinero(0)),
            )
            for config in configs
        ]

        return ResumenSplitPeriodo(
            por_socio=tuple(resumenes),
            total_agencia=total_agencia,
            total_bruto=total_bruto,
            total_comisiones_freelancer=total_comisiones_freelancer,
            ventas_count=ventas_count,
            ventas_detalle=tuple(ventas_detalle_list),
            por_freelancer=por_freelancer,
        )
