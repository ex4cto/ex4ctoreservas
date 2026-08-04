"""End-to-end integration tests for RegistrarVentaService.

Wires REAL objects end-to-end:
    RegistrarVentaService.ejecutar
    → real SQLAReglasComisionRepository.buscar_regla (SQLite in-memory)
    → real MotorComisiones.calcular

Mocked-minimal: tiqueteras (no FK chain), notificador (external I/O).

These tests guard against the class of regression caught by CRITICAL-1 in
the verify of Slice 1b: buscar_regla being called with non-Crespo punto
names and valid numero_personas, causing a step-1 miss that returned None
and raised ReglasComisionNoEncontradas for non-Crespo puntos.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from sqlalchemy.orm import Session, sessionmaker

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.valor_objetos import Participantes
from garay.infraestructura.persistencia.modelos import (
    ClienteModel,
    FreelancerModel,
    PuntoDeVentaModel,
    ReglasComisionModel,
)
from garay.infraestructura.persistencia.repositorios.comisiones_registradas import (
    SQLAComisionRegistradaRepository,
)
from garay.infraestructura.persistencia.repositorios.puntos_de_venta import (
    SQLAPuntoDeVentaRepository,
)
from garay.infraestructura.persistencia.repositorios.reglas_comision import (
    SQLAReglasComisionRepository,
)
from garay.infraestructura.persistencia.repositorios.ventas import (
    SQLAVentaRepository,
)

# ---------------------------------------------------------------------------
# DB seed helpers
# ---------------------------------------------------------------------------

_SERVICIO_ID = uuid.uuid4()
_FECHA = datetime.date(2026, 8, 1)


def _seed_db(sf: sessionmaker[Session]) -> dict[str, uuid.UUID]:
    """Seed the in-memory DB with the minimum rows needed for all integration tests."""
    cliente_id = uuid.uuid4()
    crespo_id = uuid.uuid4()
    marie_real_id = uuid.uuid4()
    vendedor_a_id = uuid.uuid4()
    vendedor_b_id = uuid.uuid4()

    with sf.begin() as session:
        # Cliente
        session.add(ClienteModel(id=cliente_id, nombre="Test Client", tipo="EXTERNO"))

        # Puntos de venta
        session.add(
            PuntoDeVentaModel(
                id=crespo_id, nombre="Crespo", porcentaje_capa=Decimal("20")
            )
        )
        session.add(
            PuntoDeVentaModel(
                id=marie_real_id, nombre="Marie Real", porcentaje_capa=Decimal("0")
            )
        )

        # Freelancers (needed for vendedor_id / cerrador_id FK)
        session.add(
            FreelancerModel(id=vendedor_a_id, nombre="Ana", activo=True, es_admin=False)
        )
        session.add(
            FreelancerModel(id=vendedor_b_id, nombre="Luis", activo=True, es_admin=False)
        )

        # Global commission rules
        session.add(
            ReglasComisionModel(
                id=uuid.uuid4(),
                tipo_cliente="EXTERNO",
                porcentaje_vendedor=Decimal("20"),
                porcentaje_cerrador=Decimal("10"),
                porcentaje_referido_maximo=Decimal("10"),
                punto_de_venta_nombre=None,
                numero_personas=None,
            )
        )
        session.add(
            ReglasComisionModel(
                id=uuid.uuid4(),
                tipo_cliente="INTERNO",
                porcentaje_vendedor=Decimal("15"),
                porcentaje_cerrador=Decimal("15"),
                porcentaje_referido_maximo=Decimal("10"),
                punto_de_venta_nombre=None,
                numero_personas=None,
            )
        )

        # Crespo point-specific rules
        session.add(
            ReglasComisionModel(
                id=uuid.uuid4(),
                tipo_cliente="EXTERNO",  # sentinel — ignored in point-specific match
                porcentaje_vendedor=Decimal("50"),
                porcentaje_cerrador=Decimal("0"),
                porcentaje_referido_maximo=Decimal("10"),
                punto_de_venta_nombre="Crespo",
                numero_personas=1,
            )
        )
        session.add(
            ReglasComisionModel(
                id=uuid.uuid4(),
                tipo_cliente="EXTERNO",  # sentinel
                porcentaje_vendedor=Decimal("30"),
                porcentaje_cerrador=Decimal("30"),
                porcentaje_referido_maximo=Decimal("10"),
                punto_de_venta_nombre="Crespo",
                numero_personas=2,
            )
        )

    return {
        "cliente_id": cliente_id,
        "crespo_id": crespo_id,
        "marie_real_id": marie_real_id,
        "vendedor_a_id": vendedor_a_id,
        "vendedor_b_id": vendedor_b_id,
    }


def _build_real_service(sf: sessionmaker[Session]) -> RegistrarVentaService:
    return RegistrarVentaService(
        ventas=SQLAVentaRepository(sf),
        reglas_repo=SQLAReglasComisionRepository(sf),
        tiqueteras=MagicMock(),  # no FK chain needed for these tests
        puntos_repo=SQLAPuntoDeVentaRepository(sf),
        motor=MotorComisiones(),
        notificador=MagicMock(),
        grupo_id="test-group",
        comisiones_repo=SQLAComisionRegistradaRepository(sf),
    )


def _cmd(
    *,
    cliente_id: uuid.UUID,
    tipo_cliente: TipoCliente = TipoCliente.EXTERNO,
    punto_de_venta_id: uuid.UUID | None,
    vendedor_id: uuid.UUID | None,
    cerrador_id: uuid.UUID | None,
    vendedor_nombre: str = "Ana",
    cerrador_nombre: str = "Luis",
    ganancia: Decimal = Decimal("100000"),
) -> RegistrarVentaComando:
    """Build a RegistrarVentaComando with the given ganancia as valor_venta - neto."""
    neto = Dinero(Decimal("100000"))
    valor_venta = Dinero(ganancia + Decimal("100000"))
    return RegistrarVentaComando(
        valor_venta=valor_venta,
        neto=neto,
        servicio_ids=[_SERVICIO_ID],
        cliente_id=cliente_id,
        tipo_cliente=tipo_cliente,
        fecha=_FECHA,
        participantes=Participantes(
            vendedor_nombre=vendedor_nombre,
            cerrador_nombre=cerrador_nombre,
            punto_de_venta_id=punto_de_venta_id,
            vendedor_id=vendedor_id,
            cerrador_id=cerrador_id,
        ),
        adultos=2,
        ninos=0,
        porcentaje_referido=Decimal("0"),
        servicio_nombres=["Test Destino"],
    )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestRegistrarVentaIntegracion:
    """End-to-end integration: real repo + real motor, SQLite in-memory."""

    def test_crespo_1_persona_montos_correctos(self, sf: sessionmaker[Session]) -> None:
        """Crespo 1-persona sale (same freelancer both roles) yields
        vendedor=50000, cerrador=0, capa=20000, agencia=30000 (ganancia=100000).
        REQ-01 / T1 via real repo + real motor.
        """
        ids = _seed_db(sf)
        service = _build_real_service(sf)
        uid = ids["vendedor_a_id"]

        resultado = service.ejecutar(
            _cmd(
                cliente_id=ids["cliente_id"],
                punto_de_venta_id=ids["crespo_id"],
                vendedor_id=uid,
                cerrador_id=uid,  # same person → 1
                vendedor_nombre="Ana",
                cerrador_nombre="Ana",
                ganancia=Decimal("100000"),
            )
        )

        d = resultado.desglose
        assert d.vendedor == Dinero("50000.00")
        assert d.cerrador == Dinero("0.00")
        assert d.punto_de_venta == Dinero("20000.00")
        assert d.agencia == Dinero("30000.00")
        assert d.vendedor + d.cerrador + d.punto_de_venta + d.agencia == Dinero("100000.00")

    def test_crespo_2_personas_montos_correctos(self, sf: sessionmaker[Session]) -> None:
        """Crespo 2-personas sale yields vendedor=30000, cerrador=30000, capa=20000, agencia=20000.
        REQ-02 / T2 via real repo + real motor.
        """
        ids = _seed_db(sf)
        service = _build_real_service(sf)

        resultado = service.ejecutar(
            _cmd(
                cliente_id=ids["cliente_id"],
                punto_de_venta_id=ids["crespo_id"],
                vendedor_id=ids["vendedor_a_id"],
                cerrador_id=ids["vendedor_b_id"],  # distinct → 2
                vendedor_nombre="Ana",
                cerrador_nombre="Luis",
                ganancia=Decimal("100000"),
            )
        )

        d = resultado.desglose
        assert d.vendedor == Dinero("30000.00")
        assert d.cerrador == Dinero("30000.00")
        assert d.punto_de_venta == Dinero("20000.00")
        assert d.agencia == Dinero("20000.00")
        assert d.vendedor + d.cerrador + d.punto_de_venta + d.agencia == Dinero("100000.00")

    def test_non_crespo_2_participants_resolves_global_rule_and_does_not_raise(
        self, sf: sessionmaker[Session]
    ) -> None:
        """CRITICAL-1 regression guard (REQ-08b):
        A non-Crespo punto (Marie Real) with both vendedor_id and cerrador_id
        set and distinct must resolve the global EXTERNO rule and succeed.

        Before the Crespo gate fix in servicio.py, this scenario called
        buscar_regla(EXTERNO, 'Marie Real', 2), which hit step-1, found no
        point-specific row, returned None, and raised ReglasComisionNoEncontradas.
        """
        ids = _seed_db(sf)
        service = _build_real_service(sf)

        # Must NOT raise
        resultado = service.ejecutar(
            _cmd(
                cliente_id=ids["cliente_id"],
                punto_de_venta_id=ids["marie_real_id"],
                vendedor_id=ids["vendedor_a_id"],
                cerrador_id=ids["vendedor_b_id"],  # distinct — 2 participants
                vendedor_nombre="Ana",
                cerrador_nombre="Luis",
                tipo_cliente=TipoCliente.EXTERNO,
                ganancia=Decimal("100000"),
            )
        )

        # Global EXTERNO rule: 20% vendedor, 10% cerrador, 0% capa (Marie Real has no capa)
        d = resultado.desglose
        assert d.vendedor == Dinero("20000.00")
        assert d.cerrador == Dinero("10000.00")
        assert d.punto_de_venta == Dinero("0.00")
        assert d.agencia == Dinero("70000.00")
