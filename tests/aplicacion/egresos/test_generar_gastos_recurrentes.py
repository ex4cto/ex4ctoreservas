"""Tests for GenerarGastosRecurrentesService — RED phase."""

from __future__ import annotations

import calendar
import datetime
import uuid
from unittest.mock import MagicMock

from garay.aplicacion.egresos.generar_gastos_recurrentes import GenerarGastosRecurrentesService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import GastoRecurrente
from garay.dominio.conciliacion.tipos import TipoEgreso


def _gasto(nombre: str = "Arriendo", dia_mes: int = 1) -> GastoRecurrente:
    return GastoRecurrente(
        id=uuid.uuid4(),
        nombre=nombre,
        monto=Dinero("500000"),
        categoria="arriendo",
        dia_mes=dia_mes,
        activo=True,
    )


def _make_service(
    gastos: list[GastoRecurrente] | None = None,
    referencias_existentes: set[str] | None = None,
) -> tuple[GenerarGastosRecurrentesService, MagicMock, MagicMock]:
    recurrentes_repo = MagicMock()
    egreso_repo = MagicMock()
    recurrentes_repo.listar_activos.return_value = gastos or []
    refs = referencias_existentes or set()
    egreso_repo.existe_referencia.side_effect = lambda r: r in refs
    service = GenerarGastosRecurrentesService(
        recurrentes_repo=recurrentes_repo, egreso_repo=egreso_repo
    )
    return service, recurrentes_repo, egreso_repo


class TestGenerarGastosRecurrentes:
    def test_sin_gastos_activos_retorna_lista_vacia(self) -> None:
        service, _, _ = _make_service(gastos=[])
        resultado = service.generar(mes=7, año=2026)
        assert resultado == []

    def test_genera_egresos_para_cada_gasto_activo(self) -> None:
        gastos = [_gasto("Arriendo"), _gasto("Nomina", dia_mes=5)]
        service, _, egreso_repo = _make_service(gastos=gastos)
        resultado = service.generar(mes=7, año=2026)

        assert len(resultado) == 2
        assert egreso_repo.guardar.call_count == 2

    def test_egreso_generado_tiene_tipo_manual(self) -> None:
        gastos = [_gasto()]
        service, _, _ = _make_service(gastos=gastos)
        resultado = service.generar(mes=7, año=2026)
        assert resultado[0].tipo == TipoEgreso.MANUAL

    def test_egreso_generado_tiene_fecha_correcta(self) -> None:
        gastos = [_gasto(dia_mes=15)]
        service, _, _ = _make_service(gastos=gastos)
        resultado = service.generar(mes=7, año=2026)
        assert resultado[0].fecha == datetime.date(2026, 7, 15)

    def test_dia_mes_mayor_a_ultimo_dia_se_ajusta(self) -> None:
        # February has 28 days in 2026 — dia_mes=31 should become 28
        gastos = [_gasto(dia_mes=31)]
        service, _, _ = _make_service(gastos=gastos)
        resultado = service.generar(mes=2, año=2026)
        ultimo = calendar.monthrange(2026, 2)[1]
        assert resultado[0].fecha == datetime.date(2026, 2, ultimo)

    def test_idempotente_skip_si_referencia_existe(self) -> None:
        gasto = _gasto()
        ref = f"recurrente-{gasto.id}-2026-07"
        service, _, egreso_repo = _make_service(
            gastos=[gasto], referencias_existentes={ref}
        )
        resultado = service.generar(mes=7, año=2026)
        assert resultado == []
        egreso_repo.guardar.assert_not_called()

    def test_referencia_formato_correcto(self) -> None:
        gasto = _gasto()
        service, _, egreso_repo = _make_service(gastos=[gasto])
        service.generar(mes=7, año=2026)

        call_args = egreso_repo.guardar.call_args[0][0]
        expected_ref = f"recurrente-{gasto.id}-2026-07"
        assert call_args.referencia == expected_ref

    def test_egreso_tiene_monto_y_descripcion_del_gasto(self) -> None:
        gasto = GastoRecurrente(
            id=uuid.uuid4(),
            nombre="Servicio internet",
            monto=Dinero("80000"),
            categoria="otro",
            dia_mes=10,
            activo=True,
        )
        service, _, _ = _make_service(gastos=[gasto])
        resultado = service.generar(mes=7, año=2026)

        assert resultado[0].monto == Dinero("80000")
        assert "Servicio internet" in resultado[0].descripcion
