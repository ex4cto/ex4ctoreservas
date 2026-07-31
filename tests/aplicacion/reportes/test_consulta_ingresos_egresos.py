"""Tests for ConsultaIngresos/EgresosService — flattening, TDD RED phase."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

from garay.aplicacion.reportes.consulta_egresos import ConsultaEgresosService
from garay.aplicacion.reportes.consulta_ingresos import ConsultaIngresosService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.entidades import Egreso, Ingreso
from garay.dominio.conciliacion.tipos import TipoEgreso


def test_consulta_ingresos_aplana() -> None:
    ingreso = Ingreso(
        id=uuid.uuid4(),
        banco="Bancolombia",
        monto=Dinero("500000"),
        fecha=datetime.date(2026, 7, 10),
        referencia="REF-1",
        remitente="Juan",
    )
    ingresos = MagicMock()
    ingresos.listar_por_periodo.return_value = [ingreso]

    servicio = ConsultaIngresosService(ingresos=ingresos)
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert len(filas) == 1
    assert filas[0].banco == "Bancolombia"
    assert filas[0].monto == Dinero("500000")
    assert filas[0].referencia == "REF-1"
    ingresos.listar_por_periodo.assert_called_once_with(
        datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
    )


def test_consulta_egresos_aplana() -> None:
    egreso = Egreso(
        id=uuid.uuid4(),
        descripcion="Almuerzo equipo",
        monto=Dinero("80000"),
        fecha=datetime.date(2026, 7, 12),
        categoria="Alimentacion",
        tipo=TipoEgreso.MANUAL,
    )
    egresos = MagicMock()
    egresos.listar_por_periodo.return_value = [egreso]

    servicio = ConsultaEgresosService(egresos=egresos)
    filas = servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))

    assert len(filas) == 1
    assert filas[0].descripcion == "Almuerzo equipo"
    assert filas[0].monto == Dinero("80000")
    assert filas[0].categoria == "Alimentacion"
    assert filas[0].tipo == "manual"


def test_consulta_ingresos_sin_datos() -> None:
    ingresos = MagicMock()
    ingresos.listar_por_periodo.return_value = []
    servicio = ConsultaIngresosService(ingresos=ingresos)
    assert servicio.ejecutar(datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)) == []
