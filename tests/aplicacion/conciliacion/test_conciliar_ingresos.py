"""Tests for ConciliarIngresosService."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.conciliacion.entidades import Ingreso, ResultadoConciliacion
from garay.dominio.conciliacion.motor import MotorConciliacion
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes

if TYPE_CHECKING:
    from garay.aplicacion.conciliacion.conciliar_ingresos import (
        ConciliarIngresosService,
    )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_HOY = datetime.date(2026, 7, 1)


def _motor() -> MotorConciliacion:
    return MotorConciliacion(
        tolerancia_pct=Decimal("0.05"),
        ventana_dias=3,
        confianza_auto=Decimal("0.90"),
        peso_monto=Decimal("0.6"),
        peso_fecha=Decimal("0.4"),
    )


def _make_ingreso(monto: int = 100_000, fecha: datetime.date = _HOY) -> Ingreso:
    return Ingreso(
        id=uuid.uuid4(),
        banco="Bancolombia",
        monto=Dinero(monto),
        fecha=fecha,
        referencia=f"REF-{uuid.uuid4().hex[:6]}",
    )


def _make_venta(valor: int = 100_000, fecha: datetime.date = _HOY) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(valor),
        neto=Dinero(valor),
        servicio_ids=[],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=fecha,
        participantes=Participantes(),
    )


def _make_ingresos_repo(ingresos: list[Ingreso]) -> MagicMock:
    repo = MagicMock()
    repo.listar_sin_clasificar.return_value = ingresos
    return repo


def _make_ventas_repo(ventas: list[Venta]) -> MagicMock:
    repo = MagicMock()
    repo.listar_por_periodo.return_value = ventas
    return repo


def _make_conciliaciones_repo(procesados: list[uuid.UUID] | None = None) -> MagicMock:
    repo = MagicMock()
    repo.listar_ingreso_ids_procesados.return_value = procesados or []
    repo.guardar.return_value = None
    return repo


def _make_service(
    ingresos_repo: MagicMock,
    ventas_repo: MagicMock,
    conciliaciones_repo: MagicMock,
    motor: MotorConciliacion | None = None,
    ventana_dias: int = 3,
) -> ConciliarIngresosService:
    from garay.aplicacion.conciliacion.conciliar_ingresos import ConciliarIngresosService

    return ConciliarIngresosService(
        ingresos=ingresos_repo,
        ventas=ventas_repo,
        conciliaciones=conciliaciones_repo,
        motor=motor or _motor(),
        ventana_dias=ventana_dias,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sin_ingresos_pendientes_devuelve_ceros() -> None:
    """No unclassified ingresos → ResultadoConciliacion(0, 0, 0)."""
    service = _make_service(
        _make_ingresos_repo([]),
        _make_ventas_repo([]),
        _make_conciliaciones_repo(),
    )
    resultado = service.ejecutar()
    assert resultado == ResultadoConciliacion(matcheados=0, sin_match=0, pendientes=0)


def test_todos_ya_procesados_devuelve_ceros() -> None:
    """All ingresos already have conciliaciones → no new processing."""
    ingreso = _make_ingreso()
    service = _make_service(
        _make_ingresos_repo([ingreso]),
        _make_ventas_repo([]),
        _make_conciliaciones_repo(procesados=[ingreso.id]),
    )
    resultado = service.ejecutar()
    assert resultado == ResultadoConciliacion(matcheados=0, sin_match=0, pendientes=0)


def test_happy_path_match_exacto() -> None:
    """1 ingreso, 1 venta con mismo monto y fecha → 1 matcheado."""
    ingreso = _make_ingreso(monto=100_000, fecha=_HOY)
    venta = _make_venta(valor=100_000, fecha=_HOY)

    ingresos_repo = _make_ingresos_repo([ingreso])
    ventas_repo = _make_ventas_repo([venta])
    conciliaciones_repo = _make_conciliaciones_repo()

    service = _make_service(ingresos_repo, ventas_repo, conciliaciones_repo)
    resultado = service.ejecutar()

    assert resultado.matcheados == 1
    assert resultado.sin_match == 0
    assert resultado.pendientes == 0
    conciliaciones_repo.guardar.assert_called_once()


def test_ventas_cargadas_una_sola_vez_no_n_mas_1() -> None:
    """With N ingresos, ventas repo is called exactly ONCE (no N+1)."""
    ingresos = [_make_ingreso() for _ in range(5)]
    ventas_repo = _make_ventas_repo([])
    ingresos_repo = _make_ingresos_repo(ingresos)
    conciliaciones_repo = _make_conciliaciones_repo()

    service = _make_service(ingresos_repo, ventas_repo, conciliaciones_repo)
    service.ejecutar()

    ventas_repo.listar_por_periodo.assert_called_once()


def test_idempotencia_no_duplica_conciliaciones() -> None:
    """Calling ejecutar twice for already-processed ingreso → no duplicate guardar."""
    ingreso = _make_ingreso()
    # First call: ingreso is not processed
    conciliaciones_repo = _make_conciliaciones_repo()
    ingresos_repo = _make_ingresos_repo([ingreso])
    ventas_repo = _make_ventas_repo([])

    service = _make_service(ingresos_repo, ventas_repo, conciliaciones_repo)
    service.ejecutar()
    assert conciliaciones_repo.guardar.call_count == 1

    # Second call: simulate ingreso now in processed list
    conciliaciones_repo2 = _make_conciliaciones_repo(procesados=[ingreso.id])
    ingresos_repo2 = _make_ingresos_repo([ingreso])
    service2 = _make_service(ingresos_repo2, ventas_repo, conciliaciones_repo2)
    service2.ejecutar()
    conciliaciones_repo2.guardar.assert_not_called()


def test_ingreso_sin_match_contabilizado() -> None:
    """Ingreso with no matching venta → sin_match incremented."""
    ingreso = _make_ingreso(monto=100_000)
    venta = _make_venta(valor=200_000)  # too different → SIN_MATCH

    service = _make_service(
        _make_ingresos_repo([ingreso]),
        _make_ventas_repo([venta]),
        _make_conciliaciones_repo(),
    )
    resultado = service.ejecutar()
    assert resultado.sin_match == 1
