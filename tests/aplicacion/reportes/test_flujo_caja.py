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
    monto: int = 100_000,
    fecha: datetime.date = datetime.date(2026, 7, 10),
    banco: str = "Bancolombia",
) -> Ingreso:
    return Ingreso(
        id=uuid.uuid4(),
        banco=banco,
        monto=Dinero(monto),
        fecha=fecha,
        referencia=f"REF-{uuid.uuid4().hex[:8]}",
    )


def _make_egreso(
    monto: int = 50_000,
    categoria: str = "transporte",
    fecha: datetime.date = datetime.date(2026, 7, 15),
    destinatario: str | None = None,
) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Compra de ejemplo",
        monto=Dinero(monto),
        fecha=fecha,
        categoria=categoria,
        tipo=TipoEgreso.MANUAL,
        destinatario=destinatario,
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


class TestFlujoCajaServiceIngresosPorBanco:
    def test_ingresos_por_banco_agrupa(self) -> None:
        i1 = _make_ingreso(monto=100_000, banco="Bancolombia")
        i2 = _make_ingreso(monto=150_000, banco="Bancolombia")
        i3 = _make_ingreso(monto=200_000, banco="Nequi")
        service = _make_service(ingresos=[i1, i2, i3], egresos=[], conciliaciones=[])
        flujo = service.ejecutar(mes=7, año=2026)

        assert len(flujo.ingresos_por_banco) == 2
        bancos = {r.banco: r for r in flujo.ingresos_por_banco}
        assert bancos["Bancolombia"].cantidad == 2
        assert bancos["Bancolombia"].monto_total == Dinero(250_000)
        assert bancos["Nequi"].cantidad == 1
        assert bancos["Nequi"].monto_total == Dinero(200_000)

    def test_ingresos_por_estado_join(self) -> None:
        ing = _make_ingreso(monto=100_000, banco="Bancolombia")
        conc = _make_conciliacion(ing.id, EstadoConciliacion.MATCHEADO)
        service = _make_service(ingresos=[ing], egresos=[], conciliaciones=[conc])
        flujo = service.ejecutar(mes=7, año=2026)

        assert len(flujo.ingresos_por_estado) == 1
        assert flujo.ingresos_por_estado[0].estado == "matcheado"
        assert flujo.ingresos_por_estado[0].monto_total == Dinero(100_000)

    def test_ingresos_por_estado_ignora_ingreso_fuera_del_map(self) -> None:
        ing = _make_ingreso(monto=100_000)
        ingreso_id_externo = uuid.UUID("00000000-0000-0000-0000-000000000001")
        conc = _make_conciliacion(ingreso_id_externo, EstadoConciliacion.MATCHEADO)
        service = _make_service(ingresos=[ing], egresos=[], conciliaciones=[conc])
        flujo = service.ejecutar(mes=7, año=2026)

        assert flujo.ingresos_por_estado == ()


class TestFlujoCajaEgresosPorDestinatario:
    """Phase 11 — MONEY-CRITICAL tests for egresos_por_destinatario grouping.

    These tests enforce:
    - Reconciliation invariant: sum(buckets) == total_egresos
    - Multi-egreso same destinatario uses exact Decimal addition
    - None bucket is present and placed last
    - Month with zero egresos yields empty tuple
    - No float anywhere in the computation path
    - Multi-recipient scenario from REQ-4 spec
    """

    def test_mes_sin_egresos_produce_tupla_vacia(self) -> None:
        """Month with no egresos must yield empty tuple, no error."""
        service = _make_service(ingresos=[], egresos=[], conciliaciones=[])
        flujo = service.ejecutar(mes=7, año=2026)

        assert flujo.egresos_por_destinatario == ()

    def test_agrupacion_por_destinatario_multiples_recipients(self) -> None:
        """REQ-4 scenario: two egresos to Maria Lopez, one to Rappi, one None."""
        e1 = _make_egreso(monto=50_000, destinatario="Maria Lopez")
        e2 = _make_egreso(monto=50_000, destinatario="Maria Lopez")
        e3 = _make_egreso(monto=30_000, destinatario="Rappi")
        e4 = _make_egreso(monto=20_000, destinatario=None)
        service = _make_service(ingresos=[], egresos=[e1, e2, e3, e4], conciliaciones=[])

        flujo = service.ejecutar(mes=7, año=2026)
        dest_dict = dict(flujo.egresos_por_destinatario)

        assert dest_dict["Maria Lopez"] == Dinero(100_000)
        assert dest_dict["Rappi"] == Dinero(30_000)
        assert dest_dict[None] == Dinero(20_000)

    def test_invariante_reconciliacion(self) -> None:
        """sum(all destinatario bucket totals) must equal total_egresos (MONEY-CRITICAL)."""
        e1 = _make_egreso(monto=50_000, destinatario="Maria Lopez")
        e2 = _make_egreso(monto=30_000, destinatario="Rappi")
        e3 = _make_egreso(monto=20_000, destinatario=None)
        service = _make_service(ingresos=[], egresos=[e1, e2, e3], conciliaciones=[])

        flujo = service.ejecutar(mes=7, año=2026)
        bucket_sum = sum(
            (monto for _, monto in flujo.egresos_por_destinatario), start=Dinero(0)
        )

        assert bucket_sum == flujo.total_egresos

    def test_mismo_destinatario_suma_exacta_decimal(self) -> None:
        """5 egresos to same recipient must total exactly as Decimal addition (REQ-4)."""
        amounts = [10_000, 20_000, 30_000, 40_000, 50_000]
        egresos = [_make_egreso(monto=a, destinatario="Carlos Perez") for a in amounts]
        service = _make_service(ingresos=[], egresos=egresos, conciliaciones=[])

        flujo = service.ejecutar(mes=7, año=2026)
        dest_dict = dict(flujo.egresos_por_destinatario)

        assert dest_dict["Carlos Perez"] == Dinero(150_000)

    def test_none_bucket_es_el_ultimo(self) -> None:
        """None bucket (sin destinatario) must appear last in the tuple."""
        e1 = _make_egreso(monto=10_000, destinatario=None)
        e2 = _make_egreso(monto=20_000, destinatario="Rappi")
        e3 = _make_egreso(monto=30_000, destinatario="ACME Corp")
        service = _make_service(ingresos=[], egresos=[e1, e2, e3], conciliaciones=[])

        flujo = service.ejecutar(mes=7, año=2026)

        last_key, _ = flujo.egresos_por_destinatario[-1]
        assert last_key is None

    def test_sin_float_en_la_ruta(self) -> None:
        """No float must appear anywhere: all values must be Decimal/Dinero."""
        from decimal import Decimal

        e1 = _make_egreso(monto=75_000, destinatario="Proveedor A")
        e2 = _make_egreso(monto=25_000, destinatario=None)
        service = _make_service(ingresos=[], egresos=[e1, e2], conciliaciones=[])

        flujo = service.ejecutar(mes=7, año=2026)

        for _, dinero in flujo.egresos_por_destinatario:
            # dinero.monto must be Decimal, not float
            assert isinstance(dinero.monto, Decimal), (
                f"Expected Decimal, got {type(dinero.monto).__name__}"
            )
            assert not isinstance(dinero.monto, float)

    def test_invariante_reconciliacion_con_solo_none(self) -> None:
        """When all egresos have destinatario=None, single bucket == total_egresos."""
        e1 = _make_egreso(monto=40_000, destinatario=None)
        e2 = _make_egreso(monto=60_000, destinatario=None)
        service = _make_service(ingresos=[], egresos=[e1, e2], conciliaciones=[])

        flujo = service.ejecutar(mes=7, año=2026)

        assert len(flujo.egresos_por_destinatario) == 1
        key, total = flujo.egresos_por_destinatario[0]
        assert key is None
        assert total == Dinero(100_000)
        assert total == flujo.total_egresos

    def test_egresos_por_destinatario_es_tupla_de_tuplas(self) -> None:
        """Result must be a tuple of 2-tuples (str | None, Dinero)."""
        e1 = _make_egreso(monto=50_000, destinatario="Rappi")
        service = _make_service(ingresos=[], egresos=[e1], conciliaciones=[])

        flujo = service.ejecutar(mes=7, año=2026)

        assert isinstance(flujo.egresos_por_destinatario, tuple)
        for item in flujo.egresos_por_destinatario:
            assert isinstance(item, tuple)
            assert len(item) == 2
            key, dinero = item
            assert key is None or isinstance(key, str)
            assert isinstance(dinero, Dinero)
