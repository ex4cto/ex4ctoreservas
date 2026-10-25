from __future__ import annotations

from decimal import Decimal

from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comisiones.servicio import MotorComisionesBase
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.ventas.entidades import Venta

_DIEZ = Decimal("10")
_NOVENTA = Decimal("90")


class MotorComisiones(MotorComisionesBase):
    """Implementacion concreta del motor de comisiones de Garay Tours."""

    def calcular(
        self,
        venta: Venta,
        reglas: ReglasComision,
        punto: PuntoDeVenta | None,
    ) -> DesgloseComision:
        snapshot = SnapshotReglas.desde_reglas(reglas, punto)

        # 1. Comision punto (se descuenta primero de ganancia)
        comision_punto = (
            venta.ganancia.aplicar_porcentaje(snapshot.porcentaje_capa_punto)
            if punto is not None
            else Dinero(0, venta.ganancia.moneda)
        )

        # 2. Comision vendedor bruto (solo si hay vendedor)
        comision_vendedor = (
            venta.ganancia.aplicar_porcentaje(snapshot.porcentaje_vendedor)
            if venta.participantes.vendedor_nombre is not None
            else Dinero(0, venta.ganancia.moneda)
        )

        # 3. Comision cerrador bruto (solo si hay cerrador)
        comision_cerrador = (
            venta.ganancia.aplicar_porcentaje(snapshot.porcentaje_cerrador)
            if venta.participantes.cerrador_nombre is not None
            else Dinero(0, venta.ganancia.moneda)
        )

        # 4. Comision agencia = residual (garantiza que el invariante se cumpla exactamente)
        comision_agencia = venta.ganancia - comision_punto - comision_vendedor - comision_cerrador

        # 5. Referido math: 10% of each bruto; neto = bruto * 0.90
        referido_alias = venta.participantes.referido_alias
        if referido_alias is not None:
            comision_referido = (
                comision_vendedor.aplicar_porcentaje(_DIEZ)
                + comision_cerrador.aplicar_porcentaje(_DIEZ)
            )
            neto_vendedor = comision_vendedor.aplicar_porcentaje(_NOVENTA)
            neto_cerrador = comision_cerrador.aplicar_porcentaje(_NOVENTA)
        else:
            comision_referido = Dinero(0, venta.ganancia.moneda)
            neto_vendedor = comision_vendedor
            neto_cerrador = comision_cerrador

        # Invariante sagrado: punto + vendedor + cerrador + agencia == ganancia
        total_neto = comision_punto + comision_vendedor + comision_cerrador + comision_agencia
        assert total_neto == venta.ganancia, f"Invariante violado: {total_neto} != {venta.ganancia}"

        return DesgloseComision(
            vendedor=comision_vendedor,
            cerrador=comision_cerrador,
            punto_de_venta=comision_punto,
            referido=comision_referido,
            agencia=comision_agencia,
            snapshot=snapshot,
            neto_vendedor=neto_vendedor,
            neto_cerrador=neto_cerrador,
        )
