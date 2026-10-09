"""Tests for LiquidarFreelancerService.calcular()."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.liquidaciones.entidades import PagoFreelancer
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.servicios.entidades import Servicio
from garay.aplicacion.liquidaciones.servicio import (
    LiquidarFreelancerService,
    RegistrarPagoFreelancerComando,
    ResultadoCalculoLiquidacion,
    _dias_solapados,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_freelancer(nombre: str = "Ana", telegram_id: int | None = None) -> Freelancer:
    return Freelancer(id=uuid.uuid4(), nombre=nombre, telegram_user_id=telegram_id)


def _make_venta(
    fecha: datetime.date,
    vendedor_nombre: str | None = None,
    cerrador_nombre: str | None = None,
    comision_vendedor: Dinero | None = None,
    comision_cerrador: Dinero | None = None,
    servicio_ids: list[uuid.UUID] | None = None,
) -> tuple[Venta, ComisionRegistrada]:
    venta_id = uuid.uuid4()
    sid = (servicio_ids or [uuid.uuid4()])[0]
    venta = Venta(
        id=venta_id,
        valor_venta=Dinero(200_000),
        neto=Dinero(100_000),
        servicio_ids=[sid],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=fecha,
        participantes=Participantes(
            vendedor_nombre=vendedor_nombre,
            cerrador_nombre=cerrador_nombre,
        ),
        adultos=2,
        ninos=0,
    )
    snapshot = SnapshotReglas(
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("10"),
        porcentaje_cerrador=Decimal("5"),
        porcentaje_referido_maximo=Decimal("0"),
        porcentaje_capa_punto=Decimal("0"),
        punto_de_venta_nombre=None,
        numero_personas=None,
    )
    comision = ComisionRegistrada(
        venta_id=venta_id,
        desglose=DesgloseComision(
            vendedor=comision_vendedor or Dinero(0),
            cerrador=comision_cerrador or Dinero(0),
            punto_de_venta=Dinero(0),
            referido=Dinero(0),
            agencia=Dinero(0),
            snapshot=snapshot,
        ),
        fecha=fecha,
    )
    return venta, comision


def _make_service(
    freelancer: Freelancer,
    ventas: list[Venta],
    comisiones: list[ComisionRegistrada],
    solapados: list[PagoFreelancer] | None = None,
    servicios: list | None = None,
) -> LiquidarFreelancerService:
    fl_repo = MagicMock()
    fl_repo.buscar_por_id.return_value = freelancer

    ventas_repo = MagicMock()
    ventas_repo.listar_por_periodo.return_value = ventas

    comisiones_repo = MagicMock()
    comisiones_repo.listar_por_venta_ids.return_value = comisiones

    # Simple plain mock with id and nombre set — no spec restriction
    default_servicio = MagicMock()
    default_servicio.id = uuid.uuid4()
    default_servicio.nombre = "Isla Palma"
    servicio_repo = MagicMock()
    servicio_repo.listar_activos.return_value = servicios if servicios is not None else [default_servicio]

    pago_repo = MagicMock()
    pago_repo.buscar_solapados.return_value = solapados or []

    return LiquidarFreelancerService(
        freelancer_repo=fl_repo,
        ventas_repo=ventas_repo,
        comisiones_repo=comisiones_repo,
        servicios_repo=servicio_repo,
        pago_repo=pago_repo,
    )


# ---------------------------------------------------------------------------
# Tests for calcular()
# ---------------------------------------------------------------------------

class TestCalcular:
    def test_returns_empty_desglose_when_no_ventas(self) -> None:
        freelancer = _make_freelancer("Ana")
        service = _make_service(freelancer, ventas=[], comisiones=[])

        result = service.calcular(
            freelancer.id,
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 7),
        )

        assert result.freelancer_nombre == "Ana"
        assert result.comisiones_total == Dinero(0)
        assert result.desglose == []

    def test_returns_correct_comision_for_vendedor(self) -> None:
        freelancer = _make_freelancer("Ana")
        sid = uuid.uuid4()
        venta, comision = _make_venta(
            fecha=datetime.date(2026, 10, 3),
            vendedor_nombre="Ana",
            comision_vendedor=Dinero(80_000),
            servicio_ids=[sid],
        )
        # Give the servicio a known id
        servicio = MagicMock()
        servicio.id = sid
        servicio.nombre = "Isla Palma"

        service = _make_service(
            freelancer, ventas=[venta], comisiones=[comision], servicios=[servicio]
        )

        result = service.calcular(
            freelancer.id,
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 7),
        )

        assert len(result.desglose) == 1
        assert result.desglose[0].comision == Dinero(80_000)
        assert result.comisiones_total == Dinero(80_000)

    def test_returns_correct_comision_for_cerrador(self) -> None:
        freelancer = _make_freelancer("Ana")
        sid = uuid.uuid4()
        venta, comision = _make_venta(
            fecha=datetime.date(2026, 10, 3),
            cerrador_nombre="Ana",
            comision_cerrador=Dinero(50_000),
            servicio_ids=[sid],
        )
        servicio = MagicMock()
        servicio.id = sid
        servicio.nombre = "Tour X"

        service = _make_service(
            freelancer, ventas=[venta], comisiones=[comision], servicios=[servicio]
        )

        result = service.calcular(
            freelancer.id,
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 7),
        )

        assert len(result.desglose) == 1
        assert result.desglose[0].comision == Dinero(50_000)

    def test_skips_venta_where_freelancer_is_neither_vendedor_nor_cerrador(self) -> None:
        freelancer = _make_freelancer("Ana")
        venta, comision = _make_venta(
            fecha=datetime.date(2026, 10, 3),
            vendedor_nombre="Carlos",
            cerrador_nombre="Maria",
            comision_vendedor=Dinero(40_000),
        )
        service = _make_service(freelancer, ventas=[venta], comisiones=[comision])

        result = service.calcular(
            freelancer.id,
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 7),
        )

        assert result.desglose == []
        assert result.comisiones_total == Dinero(0)

    def test_returns_solapados_from_pago_repo(self) -> None:
        freelancer = _make_freelancer("Ana")
        pago_anterior = PagoFreelancer(
            id=uuid.uuid4(),
            freelancer_id=freelancer.id,
            monto=Dinero(100_000),
            desde=datetime.date(2026, 9, 25),
            hasta=datetime.date(2026, 10, 5),
            fecha_pago=datetime.datetime(2026, 10, 6, tzinfo=datetime.timezone.utc),
            registrado_por_telegram_id=5870211102,
            registrado_por_nombre="Ryan",
        )
        service = _make_service(freelancer, ventas=[], comisiones=[], solapados=[pago_anterior])

        result = service.calcular(
            freelancer.id,
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 7),
        )

        assert len(result.solapados) == 1
        assert result.solapados[0] == pago_anterior


# ---------------------------------------------------------------------------
# Tests for overlap helper
# ---------------------------------------------------------------------------

class TestDiasSolapados:
    def test_overlapping_periods(self) -> None:
        """[01, 07] and query [05, 12] → overlap on 05, 06, 07."""
        dias = _dias_solapados(
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 7),
            datetime.date(2026, 10, 5),
            datetime.date(2026, 10, 12),
        )
        assert len(dias) == 3
        assert datetime.date(2026, 10, 5) in dias
        assert datetime.date(2026, 10, 7) in dias

    def test_non_overlapping_periods(self) -> None:
        """[01, 04] and query [05, 12] → no overlap."""
        dias = _dias_solapados(
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 4),
            datetime.date(2026, 10, 5),
            datetime.date(2026, 10, 12),
        )
        assert dias == []

    def test_adjacent_periods_no_overlap(self) -> None:
        """[01, 04] and [04, 08] → share only day 4."""
        dias = _dias_solapados(
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 4),
            datetime.date(2026, 10, 4),
            datetime.date(2026, 10, 8),
        )
        assert len(dias) == 1
        assert datetime.date(2026, 10, 4) in dias
