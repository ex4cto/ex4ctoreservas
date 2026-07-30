"""Tests for MovimientosRecientesService — RED phase."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

from garay.aplicacion.reportes.movimientos_recientes import (
    MovimientosRecientes,
    MovimientosRecientesService,
)
from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso, Ingreso
from garay.dominio.conciliacion.tipos import TipoEgreso

_UTC = datetime.UTC


def _ingreso(monto: str = "100000", reenviado: bool = False) -> Ingreso:
    return Ingreso(
        id=uuid.uuid4(),
        banco="Bancolombia",
        monto=Dinero(monto),
        fecha=datetime.date(2026, 7, 30),
        referencia=f"MSG-{uuid.uuid4().hex[:8]}",
        reenviado=reenviado,
    )


def _egreso(monto: str = "50000", reenviado: bool = False) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Compra varia",
        monto=Dinero(monto),
        fecha=datetime.date(2026, 7, 30),
        categoria="otro",
        tipo=TipoEgreso.AUTOMATICO,
        reenviado=reenviado,
    )


def _make_service(
    ingresos: list[Ingreso] | None = None,
    egresos: list[Egreso] | None = None,
) -> MovimientosRecientesService:
    ingreso_repo = MagicMock()
    egreso_repo = MagicMock()
    ingreso_repo.listar_recientes.return_value = ingresos or []
    egreso_repo.listar_recientes.return_value = egresos or []
    return MovimientosRecientesService(
        ingresos_repo=ingreso_repo,
        egresos_repo=egreso_repo,
    )


class TestMovimientosRecientes:
    def test_ventana_horas_se_convierte_a_minutos(self) -> None:
        ingreso_repo = MagicMock()
        egreso_repo = MagicMock()
        ingreso_repo.listar_recientes.return_value = []
        egreso_repo.listar_recientes.return_value = []
        service = MovimientosRecientesService(
            ingresos_repo=ingreso_repo,
            egresos_repo=egreso_repo,
        )
        service.ejecutar(horas=3)

        ingreso_repo.listar_recientes.assert_called_once_with(180)
        egreso_repo.listar_recientes.assert_called_once_with(180)

    def test_caso_vacio_devuelve_dinero_cero(self) -> None:
        service = _make_service()
        resultado = service.ejecutar()

        assert resultado.total_ingresos == Dinero(0)
        assert resultado.total_egresos == Dinero(0)
        assert resultado.ingresos == ()
        assert resultado.egresos == ()

    def test_totales_calculados_correctamente(self) -> None:
        i1 = _ingreso("100000")
        i2 = _ingreso("200000")
        e1 = _egreso("30000")
        e2 = _egreso("70000")
        service = _make_service(ingresos=[i1, i2], egresos=[e1, e2])

        resultado = service.ejecutar()

        assert resultado.total_ingresos == Dinero("300000")
        assert resultado.total_egresos == Dinero("100000")

    def test_ingresos_y_egresos_son_tuplas_inmutables(self) -> None:
        i = _ingreso()
        e = _egreso()
        service = _make_service(ingresos=[i], egresos=[e])

        resultado = service.ejecutar()

        assert isinstance(resultado.ingresos, tuple)
        assert isinstance(resultado.egresos, tuple)
        assert resultado.ingresos[0].id == i.id
        assert resultado.egresos[0].id == e.id

    def test_resultado_es_frozen_dataclass(self) -> None:
        service = _make_service()
        resultado = service.ejecutar()
        assert isinstance(resultado, MovimientosRecientes)
        # frozen — should raise on attempt to set attribute
        try:
            resultado.total_ingresos = Dinero(999)  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except Exception as exc:
            name = type(exc).__name__
            msg = str(exc).lower()
            assert "frozen" in msg or "can't" in msg or "FrozenInstanceError" in name

    def test_horas_por_defecto_es_24(self) -> None:
        ingreso_repo = MagicMock()
        egreso_repo = MagicMock()
        ingreso_repo.listar_recientes.return_value = []
        egreso_repo.listar_recientes.return_value = []
        service = MovimientosRecientesService(
            ingresos_repo=ingreso_repo,
            egresos_repo=egreso_repo,
        )
        service.ejecutar()

        ingreso_repo.listar_recientes.assert_called_once_with(1440)
        egreso_repo.listar_recientes.assert_called_once_with(1440)
