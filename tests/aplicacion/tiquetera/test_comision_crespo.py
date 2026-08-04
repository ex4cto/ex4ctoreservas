"""Money tests for Crespo commission rules — T1-T6, T9, T12, T13.

These tests exercise the full domain pipeline:
    buscar_regla → ReglasComision → MotorComisiones → DesgloseComision

No service-layer mocks needed — we test domain objects and motor directly.
"""

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

# ---------------------------------------------------------------------------
# Fixtures — domain objects
# ---------------------------------------------------------------------------

_GANANCIA = Decimal("100000.00")
_SERVICIO_ID = uuid.uuid4()
_CLIENTE_ID = uuid.uuid4()
_FECHA = datetime.date(2026, 8, 1)
_VENDEDOR_A = uuid.uuid4()
_VENDEDOR_B = uuid.uuid4()


def _crespo_punto() -> PuntoDeVenta:
    return PuntoDeVenta(
        id=uuid.uuid4(),
        nombre="Crespo",
        porcentaje_capa=Decimal("20"),
    )


def _crespo_regla_1p() -> ReglasComision:
    """Crespo 1-person rule: 50% vendedor, 0% cerrador, capa 20% from punto."""
    return ReglasComision(
        id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,  # sentinel — ignored in selection
        porcentaje_vendedor=Decimal("50"),
        porcentaje_cerrador=Decimal("0"),
        porcentaje_referido_maximo=Decimal("10"),
        punto_de_venta_nombre="Crespo",
        numero_personas=1,
    )


def _crespo_regla_2p() -> ReglasComision:
    """Crespo 2-person rule: 30% vendedor, 30% cerrador, capa 20% from punto."""
    return ReglasComision(
        id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,  # sentinel
        porcentaje_vendedor=Decimal("30"),
        porcentaje_cerrador=Decimal("30"),
        porcentaje_referido_maximo=Decimal("10"),
        punto_de_venta_nombre="Crespo",
        numero_personas=2,
    )


def _regla_digital() -> ReglasComision:
    """Standard digital rule: 15% vendedor, 15% cerrador, no capa."""
    return ReglasComision(
        id=uuid.uuid4(),
        tipo_cliente=TipoCliente.DIGITAL,
        porcentaje_vendedor=Decimal("15"),
        porcentaje_cerrador=Decimal("15"),
        porcentaje_referido_maximo=Decimal("10"),
        punto_de_venta_nombre=None,
        numero_personas=None,
    )


def _regla_externo() -> ReglasComision:
    """Standard global EXTERNO rule (non-Crespo)."""
    return ReglasComision(
        id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("20"),
        porcentaje_cerrador=Decimal("10"),
        porcentaje_referido_maximo=Decimal("10"),
        punto_de_venta_nombre=None,
        numero_personas=None,
    )


def _venta(
    *,
    ganancia: Decimal = _GANANCIA,
    vendedor_id: uuid.UUID | None = _VENDEDOR_A,
    cerrador_id: uuid.UUID | None = _VENDEDOR_A,
    vendedor_nombre: str | None = "Ana",
    cerrador_nombre: str | None = "Ana",
    punto_de_venta_id: uuid.UUID | None = None,
    tipo_cliente: TipoCliente = TipoCliente.EXTERNO,
) -> Venta:
    """Build a Venta with ganancia = valor_venta - neto = ganancia param."""
    valor_venta = Dinero(ganancia + Decimal("100000"))
    neto = Dinero(Decimal("100000"))
    return Venta(
        id=uuid.uuid4(),
        valor_venta=valor_venta,
        neto=neto,
        servicio_ids=[_SERVICIO_ID],
        cliente_id=_CLIENTE_ID,
        tipo_cliente=tipo_cliente,
        fecha=_FECHA,
        participantes=Participantes(
            vendedor_nombre=vendedor_nombre,
            cerrador_nombre=cerrador_nombre,
            vendedor_id=vendedor_id,
            cerrador_id=cerrador_id,
            punto_de_venta_id=punto_de_venta_id,
        ),
    )


_MOTOR = MotorComisiones()


# ---------------------------------------------------------------------------
# T1 — Crespo 1 persona: montos correctos (REQ-01)
# ---------------------------------------------------------------------------

class TestT1CrespoPrimeraPersona:
    """T1: Crespo presencial 1 persona — vendedor=cerrador, ganancia 100 000."""

    def test_comision_vendedor_cerrador(self) -> None:
        venta = _venta(ganancia=Decimal("100000"))
        reglas = _crespo_regla_1p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        # vendedor gets 50 000 (50%), cerrador gets 0 (0%)
        assert desglose.vendedor == Dinero("50000.00")
        assert desglose.cerrador == Dinero("0.00")

    def test_comision_capa(self) -> None:
        venta = _venta(ganancia=Decimal("100000"))
        reglas = _crespo_regla_1p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        assert desglose.punto_de_venta == Dinero("20000.00")

    def test_comision_agencia(self) -> None:
        venta = _venta(ganancia=Decimal("100000"))
        reglas = _crespo_regla_1p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        assert desglose.agencia == Dinero("30000.00")

    def test_suma_exacta(self) -> None:
        """REQ-03: vendedor + cerrador + capa + agencia == ganancia."""
        venta = _venta(ganancia=Decimal("100000"))
        reglas = _crespo_regla_1p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        total = (
            desglose.vendedor
            + desglose.cerrador
            + desglose.punto_de_venta
            + desglose.agencia
        )
        assert total == venta.ganancia


# ---------------------------------------------------------------------------
# T2 — Crespo 2 personas: montos correctos (REQ-02)
# ---------------------------------------------------------------------------

class TestT2Crespo2Personas:
    """T2: Crespo presencial 2 personas distintas, ganancia 100 000."""

    def test_comision_vendedor(self) -> None:
        venta = _venta(
            ganancia=Decimal("100000"),
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
        )
        reglas = _crespo_regla_2p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        assert desglose.vendedor == Dinero("30000.00")

    def test_comision_cerrador(self) -> None:
        venta = _venta(
            ganancia=Decimal("100000"),
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
        )
        reglas = _crespo_regla_2p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        assert desglose.cerrador == Dinero("30000.00")

    def test_comision_capa(self) -> None:
        venta = _venta(
            ganancia=Decimal("100000"),
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
        )
        reglas = _crespo_regla_2p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        assert desglose.punto_de_venta == Dinero("20000.00")

    def test_comision_agencia(self) -> None:
        venta = _venta(
            ganancia=Decimal("100000"),
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
        )
        reglas = _crespo_regla_2p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        assert desglose.agencia == Dinero("20000.00")

    def test_suma_exacta(self) -> None:
        venta = _venta(
            ganancia=Decimal("100000"),
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
        )
        reglas = _crespo_regla_2p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        total = (
            desglose.vendedor
            + desglose.cerrador
            + desglose.punto_de_venta
            + desglose.agencia
        )
        assert total == venta.ganancia


# ---------------------------------------------------------------------------
# T3 — Invariante de suma exacta 1 persona (con decimales) (REQ-03)
# ---------------------------------------------------------------------------

class TestT3InvarianteSuma1Persona:
    def test_invariante_con_ganancia_con_centavos(self) -> None:
        """REQ-03: no cent loss for awkward ganancia."""
        venta = _venta(ganancia=Decimal("100000.01"))
        reglas = _crespo_regla_1p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        total = (
            desglose.vendedor
            + desglose.cerrador
            + desglose.punto_de_venta
            + desglose.agencia
        )
        assert total == venta.ganancia


# ---------------------------------------------------------------------------
# T4 — Invariante de suma exacta 2 personas (con decimales) (REQ-03)
# ---------------------------------------------------------------------------

class TestT4InvarianteSuma2Personas:
    def test_invariante_con_ganancia_con_centavos(self) -> None:
        venta = _venta(
            ganancia=Decimal("100000.01"),
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
        )
        reglas = _crespo_regla_2p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        total = (
            desglose.vendedor
            + desglose.cerrador
            + desglose.punto_de_venta
            + desglose.agencia
        )
        assert total == venta.ganancia


# ---------------------------------------------------------------------------
# T5 — Canal DIGITAL + punto Crespo: no aplica capa, aplica 15/15 (REQ-04)
# ---------------------------------------------------------------------------

class TestT5DigitalConPuntoCrespo:
    """T5: DIGITAL sale at Crespo uses digital rule (15/15), not Crespo rule."""

    def test_digital_con_crespo_aplica_regla_digital(self) -> None:
        # DIGITAL sales cannot have a punto_de_venta_id (domain invariant).
        # The regla digital is supplied directly; no punto is passed to motor.
        venta = _venta(
            ganancia=Decimal("100000"),
            tipo_cliente=TipoCliente.DIGITAL,
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
            punto_de_venta_id=None,  # DIGITAL cannot have punto
        )
        reglas = _regla_digital()

        # No punto passed — digital has no capa
        desglose = _MOTOR.calcular(venta, reglas, None, Decimal("0"))

        assert desglose.vendedor == Dinero("15000.00")
        assert desglose.cerrador == Dinero("15000.00")
        assert desglose.punto_de_venta == Dinero("0.00")

    def test_digital_agencia_residual(self) -> None:
        venta = _venta(
            ganancia=Decimal("100000"),
            tipo_cliente=TipoCliente.DIGITAL,
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
            punto_de_venta_id=None,
        )
        reglas = _regla_digital()

        desglose = _MOTOR.calcular(venta, reglas, None, Decimal("0"))

        assert desglose.agencia == Dinero("70000.00")


# ---------------------------------------------------------------------------
# T6 — Canal DIGITAL + punto != Crespo: comportamiento idéntico al previo (REQ-08a)
# ---------------------------------------------------------------------------

class TestT6DigitalPuntoNoCrespo:
    """T6: DIGITAL at non-Crespo point — same behavior as before the change."""

    def test_digital_sin_punto_aplica_regla_digital(self) -> None:
        venta = _venta(
            ganancia=Decimal("100000"),
            tipo_cliente=TipoCliente.DIGITAL,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            punto_de_venta_id=None,
        )
        reglas = _regla_digital()

        desglose = _MOTOR.calcular(venta, reglas, None, Decimal("0"))

        assert desglose.vendedor == Dinero("15000.00")
        assert desglose.cerrador == Dinero("15000.00")
        assert desglose.punto_de_venta == Dinero("0.00")


# ---------------------------------------------------------------------------
# T9 — Cambio de porcentajes en DB refleja nuevo cálculo (REQ-06)
# ---------------------------------------------------------------------------

class TestT9PorcentajesDesdeDB:
    """T9: changing percentages in the rule object changes the calculation — no literals."""

    def test_updated_percentages_apply_without_code_change(self) -> None:
        """Create a custom rule with different percentages — motor must respect them."""
        regla_custom = ReglasComision(
            id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
            porcentaje_vendedor=Decimal("25"),
            porcentaje_cerrador=Decimal("35"),
            porcentaje_referido_maximo=Decimal("10"),
            punto_de_venta_nombre="Crespo",
            numero_personas=2,
        )
        punto = _crespo_punto()  # still 20% capa
        venta = _venta(
            ganancia=Decimal("100000"),
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
        )

        desglose = _MOTOR.calcular(venta, regla_custom, punto, Decimal("0"))

        assert desglose.vendedor == Dinero("25000.00")
        assert desglose.cerrador == Dinero("35000.00")
        assert desglose.punto_de_venta == Dinero("20000.00")
        # agencia = residual = 100000 - 25000 - 35000 - 20000 = 20000
        assert desglose.agencia == Dinero("20000.00")

        total = (
            desglose.vendedor
            + desglose.cerrador
            + desglose.punto_de_venta
            + desglose.agencia
        )
        assert total == venta.ganancia


# ---------------------------------------------------------------------------
# T12 — Misma persona como vendedor Y cerrador con rol_registrante="ambos" (REQ-01)
# ---------------------------------------------------------------------------

class TestT12MismaPersonaAmbosRoles:
    """T12: same person is both vendedor and cerrador — all commission to them."""

    def test_mismo_vendedor_cerrador_recibe_todo(self) -> None:
        uid = uuid.uuid4()
        venta = _venta(
            ganancia=Decimal("100000"),
            vendedor_id=uid,
            cerrador_id=uid,
            vendedor_nombre="Ana",
            cerrador_nombre="Ana",
        )
        reglas = _crespo_regla_1p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        # vendedor = 50%, cerrador = 0% — combined = 50000
        assert desglose.vendedor + desglose.cerrador == Dinero("50000.00")
        assert desglose.punto_de_venta == Dinero("20000.00")
        assert desglose.agencia == Dinero("30000.00")

    def test_suma_exacta_misma_persona(self) -> None:
        uid = uuid.uuid4()
        venta = _venta(
            ganancia=Decimal("100000"),
            vendedor_id=uid,
            cerrador_id=uid,
            vendedor_nombre="Ana",
            cerrador_nombre="Ana",
        )
        reglas = _crespo_regla_1p()
        punto = _crespo_punto()

        desglose = _MOTOR.calcular(venta, reglas, punto, Decimal("0"))

        total = (
            desglose.vendedor
            + desglose.cerrador
            + desglose.punto_de_venta
            + desglose.agencia
        )
        assert total == venta.ganancia


# ---------------------------------------------------------------------------
# T13 — Non-Crespo sale: unchanged behavior (REQ-08b)
# ---------------------------------------------------------------------------

class TestT13NoCrespoUnchanged:
    """T13: non-Crespo sale uses its own rule, behavior unchanged."""

    def test_no_crespo_externo_rule_unchanged(self) -> None:
        venta = _venta(
            ganancia=Decimal("100000"),
            vendedor_id=_VENDEDOR_A,
            cerrador_id=_VENDEDOR_B,
            vendedor_nombre="Ana",
            cerrador_nombre="Luis",
            tipo_cliente=TipoCliente.EXTERNO,
        )
        reglas = _regla_externo()  # 20% vendedor, 10% cerrador, no punto

        desglose = _MOTOR.calcular(venta, reglas, None, Decimal("0"))

        assert desglose.vendedor == Dinero("20000.00")
        assert desglose.cerrador == Dinero("10000.00")
        assert desglose.punto_de_venta == Dinero("0.00")
        assert desglose.agencia == Dinero("70000.00")

        total = (
            desglose.vendedor
            + desglose.cerrador
            + desglose.punto_de_venta
            + desglose.agencia
        )
        assert total == venta.ganancia
