"""Tests for task 2.3: LiquidarReferidoService."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.liquidaciones.servicio import LiquidarReferidoService
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

_FECHA = datetime.date(2026, 10, 3)


def _make_snapshot() -> SnapshotReglas:
    return SnapshotReglas(
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("15"),
        porcentaje_cerrador=Decimal("15"),
        porcentaje_capa_punto=Decimal("0"),
    )


def _make_venta(referido_alias: str | None = "taxi") -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(1_000_000),
        neto=Dinero(400_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_FECHA,
        participantes=Participantes(
            vendedor_nombre="Ana",
            cerrador_nombre="Bob",
            referido_alias=referido_alias,
        ),
    )


def _make_comision(
    venta_id: uuid.UUID,
    *,
    referido: int = 18_000,
    neto_vendedor: int = 81_000,
    neto_cerrador: int = 81_000,
) -> ComisionRegistrada:
    return ComisionRegistrada(
        venta_id=venta_id,
        desglose=DesgloseComision(
            vendedor=Dinero(90_000),
            cerrador=Dinero(90_000),
            punto_de_venta=Dinero(0),
            referido=Dinero(referido),
            agencia=Dinero(420_000),
            snapshot=_make_snapshot(),
            neto_vendedor=Dinero(neto_vendedor),
            neto_cerrador=Dinero(neto_cerrador),
        ),
        fecha=_FECHA,
    )


def _make_service(
    ventas: list[Venta],
    comisiones: list[ComisionRegistrada],
) -> LiquidarReferidoService:
    ventas_repo = MagicMock()
    ventas_repo.listar_por_periodo.return_value = ventas
    comisiones_repo = MagicMock()
    comisiones_repo.listar_por_venta_ids.return_value = comisiones
    return LiquidarReferidoService(
        ventas_repo=ventas_repo,
        comisiones_repo=comisiones_repo,
    )


class TestLiquidarReferidoService:
    def test_suma_referido_para_alias(self) -> None:
        """Task 2.3: sum referido amounts for ventas with the given alias."""
        venta = _make_venta(referido_alias="taxi")
        comision = _make_comision(venta.id, referido=18_000)
        service = _make_service([venta], [comision])

        resultado = service.calcular(
            referido_alias="taxi",
            desde=datetime.date(2026, 10, 1),
            hasta=datetime.date(2026, 10, 7),
        )

        assert resultado.referido_alias == "taxi"
        assert resultado.total == Dinero(18_000)

    def test_filtra_ventas_con_diferente_alias(self) -> None:
        """Task 2.3: only includes ventas matching the requested alias."""
        v1 = _make_venta(referido_alias="taxi")
        v2 = _make_venta(referido_alias="moto")
        c1 = _make_comision(v1.id, referido=18_000)
        c2 = _make_comision(v2.id, referido=12_000)
        service = _make_service([v1, v2], [c1, c2])

        resultado = service.calcular(
            referido_alias="taxi",
            desde=datetime.date(2026, 10, 1),
            hasta=datetime.date(2026, 10, 7),
        )

        assert resultado.total == Dinero(18_000)

    def test_sin_ventas_retorna_cero(self) -> None:
        service = _make_service([], [])

        resultado = service.calcular(
            referido_alias="taxi",
            desde=datetime.date(2026, 10, 1),
            hasta=datetime.date(2026, 10, 7),
        )

        assert resultado.total == Dinero(0)
        assert resultado.desglose == []

    def test_excluye_ventas_sin_referido(self) -> None:
        venta = _make_venta(referido_alias=None)
        comision = _make_comision(venta.id, referido=0)
        service = _make_service([venta], [comision])

        resultado = service.calcular(
            referido_alias="taxi",
            desde=datetime.date(2026, 10, 1),
            hasta=datetime.date(2026, 10, 7),
        )

        assert resultado.total == Dinero(0)

    def test_desglose_contiene_detalle_por_venta(self) -> None:
        venta = _make_venta(referido_alias="taxi")
        comision = _make_comision(venta.id, referido=18_000)
        service = _make_service([venta], [comision])

        resultado = service.calcular(
            referido_alias="taxi",
            desde=datetime.date(2026, 10, 1),
            hasta=datetime.date(2026, 10, 7),
        )

        assert len(resultado.desglose) == 1
        assert resultado.desglose[0].referido == Dinero(18_000)
        assert resultado.desglose[0].fecha == _FECHA
