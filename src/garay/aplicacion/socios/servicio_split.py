"""SplitSociosService — calculates the historical revenue split for all partners."""

from __future__ import annotations

import datetime

from garay.aplicacion.socios.split import ResumenSocio, ResumenSplitSocios
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
