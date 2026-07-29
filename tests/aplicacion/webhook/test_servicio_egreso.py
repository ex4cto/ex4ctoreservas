"""Tests for guardar_egreso service function — RED phase."""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.webhook.servicio import guardar_egreso
from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.tipos import CategoriaEgreso, TipoEgreso
from garay.infraestructura.webhook.schemas import EgresoExtraido


def _make_egreso_extraido(
    *,
    monto: Decimal = Decimal("69328.00"),
    descripcion: str = "Compra en MOVISTAR PAGOSEPAYCO",
    banco_origen: str = "Bancolombia",
    year: int = 2026,
    month: int = 7,
    day: int = 27,
) -> EgresoExtraido:
    return EgresoExtraido(
        monto=monto,
        descripcion=descripcion,
        banco_origen=banco_origen,
        fecha_egreso=datetime.datetime(year, month, day, 18, 25, tzinfo=datetime.UTC),
    )


def test_guardar_egreso_devuelve_egreso_con_campos_correctos() -> None:
    repo = MagicMock()
    pago = _make_egreso_extraido()

    resultado = guardar_egreso(pago, "MSG-EGRESO-001", repo, moneda="COP")

    assert resultado.descripcion == "Compra en MOVISTAR PAGOSEPAYCO"
    assert resultado.monto == Dinero("69328.00", "COP")
    assert resultado.fecha == datetime.date(2026, 7, 27)
    assert resultado.categoria == CategoriaEgreso.OTRO
    assert resultado.tipo == TipoEgreso.AUTOMATICO
    assert resultado.referencia == "MSG-EGRESO-001"


def test_guardar_egreso_llama_repo_guardar() -> None:
    repo = MagicMock()
    pago = _make_egreso_extraido()

    resultado = guardar_egreso(pago, "MSG-EGRESO-002", repo, moneda="COP")

    repo.guardar.assert_called_once_with(resultado)


def test_guardar_egreso_genera_uuid_unico() -> None:
    repo = MagicMock()
    pago = _make_egreso_extraido()

    r1 = guardar_egreso(pago, "MSG-A", repo, moneda="COP")
    r2 = guardar_egreso(pago, "MSG-B", repo, moneda="COP")

    assert r1.id != r2.id


def test_guardar_egreso_nequi() -> None:
    repo = MagicMock()
    pago = _make_egreso_extraido(
        monto=Decimal("5000"),
        descripcion="Envio a BRYAN CASTRO",
        banco_origen="Nequi",
    )

    resultado = guardar_egreso(pago, "MSG-NEQUI-001", repo, moneda="COP")

    assert resultado.monto == Dinero("5000", "COP")
    assert resultado.tipo == TipoEgreso.AUTOMATICO
