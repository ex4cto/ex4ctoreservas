from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest

from garay.dominio.comisiones.errores import PorcentajeReferidoSuperaTecho
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes


def _venta(
    valor_venta: int = 1_000_000,
    neto: int = 900_000,
    tipo_cliente: TipoCliente = TipoCliente.EXTERNO,
    vendedor: str | None = "vendedor",
    cerrador: str | None = "cerrador",
    referido: str | None = None,
    punto_id: uuid.UUID | None = None,
) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(valor_venta),
        neto=Dinero(neto),
        servicio_id=uuid.uuid4(),
        cliente_id=uuid.uuid4(),
        tipo_cliente=tipo_cliente,
        fecha=datetime.date(2026, 7, 1),
        participantes=Participantes(
            vendedor_nombre=vendedor,
            cerrador_nombre=cerrador,
            punto_de_venta_id=punto_id,
            referido_nombre=referido,
        ),
    )


def _punto(porcentaje_capa: Decimal = Decimal("20")) -> PuntoDeVenta:
    return PuntoDeVenta(
        id=uuid.uuid4(),
        nombre="Punto 4",
        porcentaje_capa=porcentaje_capa,
    )


def _reglas(
    tipo_cliente: TipoCliente = TipoCliente.EXTERNO,
    porcentaje_vendedor: Decimal = Decimal("50"),
    porcentaje_cerrador: Decimal = Decimal("0"),
    porcentaje_referido_maximo: Decimal = Decimal("10"),
) -> ReglasComision:
    return ReglasComision(
        id=uuid.uuid4(),
        tipo_cliente=tipo_cliente,
        porcentaje_vendedor=porcentaje_vendedor,
        porcentaje_cerrador=porcentaje_cerrador,
        porcentaje_referido_maximo=porcentaje_referido_maximo,
    )


motor = MotorComisiones()


class TestCasoBase:
    def test_kike_solo_en_punto4(self) -> None:
        # Garay example: valor_venta=1_000_000, neto=900_000 → ganancia=100_000
        # capa=20% → punto=20_000; vendedor=50% → 50_000; cerrador=0%; agencia=30_000
        punto = _punto(Decimal("20"))
        venta = _venta(
            valor_venta=1_000_000,
            neto=900_000,
            vendedor="kike",
            cerrador="kike",
            punto_id=punto.id,
        )
        reglas = _reglas(porcentaje_vendedor=Decimal("50"), porcentaje_cerrador=Decimal("0"))

        result = motor.calcular(venta, reglas, punto)

        assert result.punto_de_venta == Dinero(20_000)
        assert result.vendedor == Dinero(50_000)
        assert result.cerrador == Dinero(0)
        assert result.agencia == Dinero(30_000)
        total = result.punto_de_venta + result.vendedor + result.cerrador + result.agencia
        assert total == venta.ganancia

    def test_sin_punto_sin_referido(self) -> None:
        # Standard case: vendedor=20%, cerrador=20%, agencia=60%
        venta = _venta(valor_venta=1_000_000, neto=900_000)
        reglas = _reglas(porcentaje_vendedor=Decimal("20"), porcentaje_cerrador=Decimal("20"))

        result = motor.calcular(venta, reglas, None)

        assert result.punto_de_venta == Dinero(0)
        assert result.vendedor == Dinero(20_000)
        assert result.cerrador == Dinero(20_000)
        assert result.agencia == Dinero(60_000)
        assert result.referido == Dinero(0)

    def test_digital_80_20(self) -> None:
        # DIGITAL: vendedor=20%, cerrador=0 (one person handles digital), agencia=80%
        venta = _venta(
            valor_venta=1_000_000,
            neto=900_000,
            tipo_cliente=TipoCliente.DIGITAL,
            cerrador=None,
        )
        reglas = _reglas(
            tipo_cliente=TipoCliente.DIGITAL,
            porcentaje_vendedor=Decimal("20"),
            porcentaje_cerrador=Decimal("0"),
        )

        result = motor.calcular(venta, reglas, None)

        assert result.vendedor == Dinero(20_000)
        assert result.cerrador == Dinero(0)
        assert result.agencia == Dinero(80_000)


class TestParticipacion:
    def test_sin_vendedor_agencia_absorbe(self) -> None:
        venta = _venta(vendedor=None, cerrador="cerrador")
        reglas = _reglas(porcentaje_vendedor=Decimal("20"), porcentaje_cerrador=Decimal("20"))

        result = motor.calcular(venta, reglas, None)

        assert result.vendedor == Dinero(0)
        assert result.cerrador == Dinero(20_000)
        # agencia absorbs vendedor's share: 60 + 20 = 80%
        assert result.agencia == Dinero(80_000)

    def test_sin_cerrador_agencia_absorbe(self) -> None:
        venta = _venta(vendedor="vendedor", cerrador=None)
        reglas = _reglas(porcentaje_vendedor=Decimal("20"), porcentaje_cerrador=Decimal("20"))

        result = motor.calcular(venta, reglas, None)

        assert result.cerrador == Dinero(0)
        assert result.vendedor == Dinero(20_000)
        # agencia absorbs cerrador's share: 60 + 20 = 80%
        assert result.agencia == Dinero(80_000)

    def test_sin_participantes_agencia_100(self) -> None:
        venta = _venta(vendedor=None, cerrador=None)
        reglas = _reglas(porcentaje_vendedor=Decimal("20"), porcentaje_cerrador=Decimal("20"))

        result = motor.calcular(venta, reglas, None)

        assert result.vendedor == Dinero(0)
        assert result.cerrador == Dinero(0)
        assert result.punto_de_venta == Dinero(0)
        assert result.agencia == venta.ganancia


class TestReferido:
    def test_referido_sobre_bruto(self) -> None:
        # referido % is applied to valor_venta (bruto), NOT ganancia
        venta = _venta(
            valor_venta=1_000_000,
            neto=900_000,
            referido="taxista",
        )
        reglas = _reglas(porcentaje_referido_maximo=Decimal("10"))

        result = motor.calcular(venta, reglas, None, porcentaje_referido=Decimal("5"))

        # 5% of 1_000_000 = 50_000, NOT 5% of 100_000 ganancia
        assert result.referido == Dinero(50_000)

    def test_referido_supera_techo_levanta_error(self) -> None:
        venta = _venta(referido="taxista")
        reglas = _reglas(porcentaje_referido_maximo=Decimal("10"))

        with pytest.raises(PorcentajeReferidoSuperaTecho):
            motor.calcular(venta, reglas, None, porcentaje_referido=Decimal("11"))

    def test_sin_referido_nombre_comision_cero(self) -> None:
        # No referido_nombre → comision_referido = 0 even if porcentaje > 0
        venta = _venta(referido=None)
        reglas = _reglas(porcentaje_referido_maximo=Decimal("10"))

        result = motor.calcular(venta, reglas, None, porcentaje_referido=Decimal("5"))

        assert result.referido == Dinero(0)


class TestInvariante:
    def test_suma_comisiones_ganancia_exacta(self) -> None:
        punto = _punto(Decimal("20"))
        venta = _venta(
            valor_venta=1_000_000,
            neto=900_000,
            vendedor="v",
            cerrador="c",
            punto_id=punto.id,
        )
        reglas = _reglas(porcentaje_vendedor=Decimal("30"), porcentaje_cerrador=Decimal("20"))

        result = motor.calcular(venta, reglas, punto)

        total = result.punto_de_venta + result.vendedor + result.cerrador + result.agencia
        assert total == venta.ganancia

    def test_residuo_redondeo_va_a_agencia(self) -> None:
        # ganancia = 100_001 with 3-way split causes rounding
        # Use a value that doesn't divide evenly by 3
        venta = _venta(valor_venta=1_000_001, neto=900_000)
        reglas = _reglas(porcentaje_vendedor=Decimal("33"), porcentaje_cerrador=Decimal("33"))

        result = motor.calcular(venta, reglas, None)

        total = result.punto_de_venta + result.vendedor + result.cerrador + result.agencia
        assert total == venta.ganancia


class TestSnapshot:
    def test_calculo_incluye_snapshot(self) -> None:
        venta = _venta()
        reglas = _reglas(tipo_cliente=TipoCliente.EXTERNO)

        result = motor.calcular(venta, reglas, None)

        assert result.snapshot.tipo_cliente == TipoCliente.EXTERNO
        assert result.snapshot.porcentaje_vendedor == reglas.porcentaje_vendedor
        assert result.snapshot.porcentaje_cerrador == reglas.porcentaje_cerrador

    def test_snapshot_captura_capa_punto(self) -> None:
        punto = _punto(Decimal("25"))
        venta = _venta(punto_id=punto.id)
        reglas = _reglas()

        result = motor.calcular(venta, reglas, punto)

        assert result.snapshot.porcentaje_capa_punto == Decimal("25")
