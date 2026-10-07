"""Tests for GenerarCuentaCobroService.buscar_ventas_isla_palma().

TDD: tests written first (RED), then implementation (GREEN).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.cuenta_cobro.servicio import GenerarCuentaCobroService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOY = datetime.date(2026, 1, 15)


def _servicio(sid: uuid.UUID, nombre: str) -> Servicio:
    return Servicio(
        id=sid,
        numero=1,
        nombre=nombre,
        descripcion="",
        activo=True,
        precio_neto_adulto=None,
        precio_neto_nino=None,
        permite_ninos=True,
        categoria="",
        horarios=[],
        netos_por_horario={},
        precio_sugerido_adulto=None,
        precio_sugerido_nino=None,
    )


def _venta(servicio_ids: list[uuid.UUID]) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(Decimal("100000")),
        neto=Dinero(Decimal("80000")),
        abono=None,
        servicio_ids=servicio_ids,
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_HOY,
        participantes=Participantes(),
        adultos=2,
        ninos=0,
    )


def _make_service(
    servicios: list[Servicio],
    ventas: list[Venta],
) -> GenerarCuentaCobroService:
    """Build a GenerarCuentaCobroService with mocked repos."""
    servicio_repo = MagicMock()
    servicio_repo.listar_activos.return_value = servicios

    ventas_repo = MagicMock()
    ventas_repo.listar_por_periodo.return_value = ventas

    contador = MagicMock()
    renderer = MagicMock()
    settings = MagicMock()

    return GenerarCuentaCobroService(
        ventas_repo=ventas_repo,
        servicio_repo=servicio_repo,
        contador=contador,
        renderer=renderer,
        assets_path=MagicMock(),
        settings=settings,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuscarVentasIslaPalma:
    """buscar_ventas_isla_palma() returns only ventas with Isla Palma services."""

    def test_returns_ventas_with_isla_palma_service(self) -> None:
        """Ventas that include an Isla Palma service are included."""
        isla_id = uuid.uuid4()
        otro_id = uuid.uuid4()

        isla = _servicio(isla_id, "ISLA PALMA — Día completo")
        otro = _servicio(otro_id, "Cartagena City Tour")

        venta_isla = _venta([isla_id])
        venta_otro = _venta([otro_id])

        svc = _make_service([isla, otro], [venta_isla, venta_otro])
        resultado = svc.buscar_ventas_isla_palma(_HOY)

        assert resultado == [venta_isla]

    def test_ignores_ventas_from_other_services_same_day(self) -> None:
        """Ventas for non-Isla-Palma services on the same day are excluded."""
        otro_id = uuid.uuid4()
        otro = _servicio(otro_id, "Palmarito Tour")

        venta = _venta([otro_id])

        svc = _make_service([otro], [venta])
        resultado = svc.buscar_ventas_isla_palma(_HOY)

        assert resultado == []

    def test_returns_empty_when_no_ventas_at_all(self) -> None:
        """When no ventas exist for the date, an empty list is returned."""
        isla_id = uuid.uuid4()
        isla = _servicio(isla_id, "ISLA PALMA — Snorkel")

        svc = _make_service([isla], [])
        resultado = svc.buscar_ventas_isla_palma(_HOY)

        assert resultado == []

    def test_returns_empty_when_no_isla_palma_services_configured(self) -> None:
        """When no Isla Palma services exist in DB, no ventas match."""
        otro_id = uuid.uuid4()
        otro = _servicio(otro_id, "Bonavida Glamping")
        venta = _venta([otro_id])

        svc = _make_service([otro], [venta])
        resultado = svc.buscar_ventas_isla_palma(_HOY)

        assert resultado == []

    def test_includes_venta_with_mixed_services_if_any_is_isla_palma(self) -> None:
        """A venta with multiple services is included when one is Isla Palma."""
        isla_id = uuid.uuid4()
        extra_id = uuid.uuid4()

        isla = _servicio(isla_id, "ISLA PALMA Combo")
        extra = _servicio(extra_id, "Snorkel Add-on")

        venta = _venta([isla_id, extra_id])

        svc = _make_service([isla, extra], [venta])
        resultado = svc.buscar_ventas_isla_palma(_HOY)

        assert resultado == [venta]
