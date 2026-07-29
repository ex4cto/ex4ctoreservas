"""Tests for FlujoCajaService — TDD RED phase."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

from garay.aplicacion.reportes.flujo_caja import FlujoCajaService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Conciliacion, Egreso, Ingreso
from garay.dominio.conciliacion.tipos import EstadoConciliacion, TipoEgreso


def _make_ingreso(
    monto: int = 100_000, fecha: datetime.date = datetime.date(2026, 7, 10)
) -> Ingreso:
    return Ingreso(
        id=uuid.uuid4(),
        banco="Bancolombia",
        monto=Dinero(monto),
        fecha=fecha,
        referencia=f"REF-{uuid.uuid4().hex[:8]}",
    )


def _make_egreso(
    monto: int = 50_000,
    categoria: str = "transporte",
    fecha: datetime.date = datetime.date(2026, 7, 15),
) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Compra de ejemplo",
        monto=Dinero(monto),
        fecha=fecha,
        categoria=categoria,
        tipo=TipoEgreso.MANUAL,
    )


def _make_conciliacion(
    ingreso_id: uuid.UUID,
    estado: EstadoConciliacion = EstadoConciliacion.PENDIENTE,
) -> Conciliacion:
    return Conciliacion(
        id=uuid.uuid4(),
        ingreso_id=ingreso_id,
        venta_id=None,
        estado=estado,
    )


def _make_service(
    ingresos: list[Ingreso],
    egresos: list[Egreso],
    conciliaciones: list[Conciliacion],
) -> FlujoCajaService:
    ing_repo = MagicMock()
    ing_repo.listar_por_periodo.return_value = ingresos

    egr_repo = MagicMock()
    egr_repo.listar_por_periodo.return_value = egresos

    conc_repo = MagicMock()
    conc_repo.listar_por_periodo.return_value = conciliaciones

    return FlujoCajaService(
        ingresos=ing_repo,
        egresos=egr_repo,
        conciliaciones=conc_repo,
    )


class TestFlujoCajaServiceSinDatos:
    def test_mes_sin_datos_devuelve_ceros(self) -> None:
        service = _make_service(ingresos=[], egresos=[], conciliaciones=[])
        flujo = service.ejecutar(mes=7, año=2026)

        assert flujo.total_ingresos == Dinero(0)
        assert flujo.total_egresos == Dinero(0)
        assert flujo.balance == Dinero(0)
        assert flujo.ingresos_conciliados == 0
        assert flujo.ingresos_pendientes == 0
        assert flujo.egresos_por_categoria == ()
        assert flujo.mes == 7
        assert flujo.año == 2026


class TestFlujoCajaServiceBalance:
    def test_balance_positivo(self) -> None:
        ing = _make_ingreso(monto=500_000)
        egr = _make_egreso(monto=200_000)
        service = _make_service(ingresos=[ing], egresos=[egr], conciliaciones=[])

        flujo = service.ejecutar(mes=7, año=2026)

        assert flujo.total_ingresos == Dinero(500_000)
        assert flujo.total_egresos == Dinero(200_000)
        assert flujo.balance == Dinero(300_000)

    def test_balance_negativo_cuando_egresos_superan_ingresos(self) -> None:
        ing = _make_ingreso(monto=100_000)
        egr = _make_egreso(monto=300_000)
        service = _make_service(ingresos=[ing], egresos=[egr], conciliaciones=[])

        flujo = service.ejecutar(mes=7, año=2026)

        assert flujo.balance.monto < 0


class TestFlujoCajaServiceCategorias:
    def test_egresos_agrupados_por_categoria(self) -> None:
        egr1 = _make_egreso(monto=50_000, categoria="transporte")
        egr2 = _make_egreso(monto=30_000, categoria="transporte")
        egr3 = _make_egreso(monto=20_000, categoria="oficina")
        service = _make_service(ingresos=[], egresos=[egr1, egr2, egr3], conciliaciones=[])

        flujo = service.ejecutar(mes=7, año=2026)

        cat_dict = dict(flujo.egresos_por_categoria)
        assert cat_dict["transporte"] == Dinero(80_000)
        assert cat_dict["oficina"] == Dinero(20_000)


class TestFlujoCajaServiceConciliados:
    def test_conteo_correcto_por_estado(self) -> None:
        ing1 = _make_ingreso()
        ing2 = _make_ingreso()
        ing3 = _make_ingreso()

        conc_matcheada = _make_conciliacion(ing1.id, EstadoConciliacion.MATCHEADO)
        conc_pendiente = _make_conciliacion(ing2.id, EstadoConciliacion.PENDIENTE)
        conc_sin_match = _make_conciliacion(ing3.id, EstadoConciliacion.SIN_MATCH)

        service = _make_service(
            ingresos=[ing1, ing2, ing3],
            egresos=[],
            conciliaciones=[conc_matcheada, conc_pendiente, conc_sin_match],
        )

        flujo = service.ejecutar(mes=7, año=2026)

        assert flujo.ingresos_conciliados == 1
        assert flujo.ingresos_pendientes == 2  # PENDIENTE + SIN_MATCH
