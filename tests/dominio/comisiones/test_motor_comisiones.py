from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

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
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=tipo_cliente,
        fecha=datetime.date(2026, 7, 1),
        participantes=Participantes(
            vendedor_nombre=vendedor,
            cerrador_nombre=cerrador,
            punto_de_venta_id=punto_id,
            referido_alias=referido,
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
) -> ReglasComision:
    return ReglasComision(
        id=uuid.uuid4(),
        tipo_cliente=tipo_cliente,
        porcentaje_vendedor=porcentaje_vendedor,
        porcentaje_cerrador=porcentaje_cerrador,
    )

motor = MotorComisiones()

class TestCasoBase:
    def test_kike_solo_en_punto4(self) -> None:
        # ganancia=100_000; capa=20% -> punto=20_000; vendedor=50% -> 50_000; agencia=30_000
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
        venta = _venta(valor_venta=1_000_000, neto=900_000)
        reglas = _reglas(porcentaje_vendedor=Decimal("20"), porcentaje_cerrador=Decimal("20"))

        result = motor.calcular(venta, reglas, None)

        assert result.punto_de_venta == Dinero(0)
        assert result.vendedor == Dinero(20_000)
        assert result.cerrador == Dinero(20_000)
        assert result.agencia == Dinero(60_000)
        assert result.referido == Dinero(0)

    def test_digital_80_20(self) -> None:
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
        assert result.agencia == Dinero(80_000)

    def test_sin_cerrador_agencia_absorbe(self) -> None:
        venta = _venta(vendedor="vendedor", cerrador=None)
        reglas = _reglas(porcentaje_vendedor=Decimal("20"), porcentaje_cerrador=Decimal("20"))

        result = motor.calcular(venta, reglas, None)

        assert result.cerrador == Dinero(0)
        assert result.vendedor == Dinero(20_000)
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
    """Task 1.5: New referido math -- 10% of each bruto; neto = bruto * 0.90."""

    def test_vendedor_distinto_cerrador_con_referido(self) -> None:
        # ganancia=600_000 (valor=1_000_000, neto=400_000)
        # vendedor_bruto = 600_000 * 0.15 = 90_000
        # cerrador_bruto = 600_000 * 0.15 = 90_000
        # referido = 90_000*0.10 + 90_000*0.10 = 18_000
        # neto_vendedor = neto_cerrador = 81_000
        venta = _venta(
            valor_venta=1_000_000,
            neto=400_000,
            vendedor="Ana",
            cerrador="Bob",
            referido="taxi",
        )
        reglas = _reglas(
            porcentaje_vendedor=Decimal("15"),
            porcentaje_cerrador=Decimal("15"),
        )

        result = motor.calcular(venta, reglas, None)

        assert result.referido == Dinero(18_000)
        assert result.neto_vendedor == Dinero(81_000)
        assert result.neto_cerrador == Dinero(81_000)
        assert result.vendedor == Dinero(90_000)
        assert result.cerrador == Dinero(90_000)

    def test_vendedor_igual_cerrador_con_referido(self) -> None:
        venta = _venta(
            valor_venta=1_000_000,
            neto=400_000,
            vendedor="Ana",
            cerrador="Ana",
            referido="taxi",
        )
        reglas = _reglas(
            porcentaje_vendedor=Decimal("15"),
            porcentaje_cerrador=Decimal("15"),
        )

        result = motor.calcular(venta, reglas, None)

        assert result.referido == Dinero(18_000)
        assert result.neto_vendedor == Dinero(81_000)
        assert result.neto_cerrador == Dinero(81_000)

    def test_sin_referido_neto_igual_bruto(self) -> None:
        venta = _venta(
            valor_venta=1_000_000,
            neto=400_000,
            vendedor="Ana",
            cerrador="Bob",
            referido=None,
        )
        reglas = _reglas(
            porcentaje_vendedor=Decimal("15"),
            porcentaje_cerrador=Decimal("15"),
        )

        result = motor.calcular(venta, reglas, None)

        assert result.referido == Dinero(0)
        assert result.neto_vendedor == result.vendedor
        assert result.neto_cerrador == result.cerrador

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

    def test_invariante_con_referido(self) -> None:
        # Referido does NOT affect punto+vendedor+cerrador+agencia==ganancia invariant
        venta = _venta(
            valor_venta=1_000_000,
            neto=400_000,
            vendedor="Ana",
            cerrador="Bob",
            referido="taxi",
        )
        reglas = _reglas(
            porcentaje_vendedor=Decimal("15"),
            porcentaje_cerrador=Decimal("15"),
        )

        result = motor.calcular(venta, reglas, None)

        total = result.punto_de_venta + result.vendedor + result.cerrador + result.agencia
        assert total == venta.ganancia

    def test_residuo_redondeo_va_a_agencia(self) -> None:
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
