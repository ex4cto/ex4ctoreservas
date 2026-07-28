from __future__ import annotations

from decimal import Decimal

from garay.dominio.comisiones.errores import PorcentajeReferidoSuperaTecho
from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comisiones.servicio import MotorComisionesBase
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.ventas.entidades import Venta

_CERO = Decimal("0")


class MotorComisiones(MotorComisionesBase):
    """Implementacion concreta del motor de comisiones de Garay Tours."""

    def calcular(
        self,
        venta: Venta,
        reglas: ReglasComision,
        punto: PuntoDeVenta | None,
        porcentaje_referido: Decimal = _CERO,
    ) -> DesgloseComision:
        if porcentaje_referido > reglas.porcentaje_referido_maximo:
            raise PorcentajeReferidoSuperaTecho(
                f"El porcentaje de referido ({porcentaje_referido}%) supera el maximo "
                f"permitido ({reglas.porcentaje_referido_maximo}%)."
            )

        snapshot = SnapshotReglas.desde_reglas(reglas, punto)

        # 1. Comision punto (se descuenta primero de ganancia)
        comision_punto = (
            venta.ganancia.aplicar_porcentaje(snapshot.porcentaje_capa_punto)
            if punto is not None
            else Dinero(0, venta.ganancia.moneda)
        )

        # 2. Comision vendedor (solo si hay vendedor)
        comision_vendedor = (
            venta.ganancia.aplicar_porcentaje(snapshot.porcentaje_vendedor)
            if venta.participantes.vendedor_nombre is not None
            else Dinero(0, venta.ganancia.moneda)
        )

        # 3. Comision cerrador (solo si hay cerrador)
        comision_cerrador = (
            venta.ganancia.aplicar_porcentaje(snapshot.porcentaje_cerrador)
            if venta.participantes.cerrador_nombre is not None
            else Dinero(0, venta.ganancia.moneda)
        )

        # 4. Comision agencia = residual (garantiza que el invariante se cumpla exactamente)
        comision_agencia = venta.ganancia - comision_punto - comision_vendedor - comision_cerrador

        # 5. Comision referido: sobre valor_venta (bruto), independiente de ganancia
        comision_referido = (
            venta.valor_venta.aplicar_porcentaje(porcentaje_referido)
            if venta.participantes.referido_nombre is not None
            else Dinero(0, venta.valor_venta.moneda)
        )

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
        )
