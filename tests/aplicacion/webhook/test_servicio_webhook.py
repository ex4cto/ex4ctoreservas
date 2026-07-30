"""Tests for guardar_ingreso service function — TDD RED phase."""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.webhook.servicio import guardar_ingreso
from garay.dominio.comun.dinero import Dinero
from garay.infraestructura.webhook.schemas import PagoExtraido


def _make_pago(
    *,
    monto: Decimal = Decimal("500000"),
    remitente: str = "Juan Perez",
    banco_origen: str = "Bancolombia",
    year: int = 2026,
    month: int = 7,
    day: int = 15,
) -> PagoExtraido:
    return PagoExtraido(
        monto=monto,
        remitente=remitente,
        banco_origen=banco_origen,
        fecha_pago=datetime.datetime(year, month, day, 10, 30, tzinfo=datetime.UTC),
    )


def test_guardar_ingreso_devuelve_ingreso_con_campos_correctos() -> None:
    repo = MagicMock()
    pago = _make_pago()

    resultado = guardar_ingreso(pago, "MSG-001", repo, moneda="COP")

    assert resultado.banco == "Bancolombia"
    assert resultado.monto == Dinero("500000", "COP")
    assert resultado.referencia == "MSG-001"
    assert resultado.remitente == "Juan Perez"
    assert resultado.clasificado is False
    assert resultado.fecha == datetime.date(2026, 7, 15)
    assert resultado.correo_origen is None
    assert resultado.reenviado is False


def test_guardar_ingreso_pasa_correo_origen_y_reenviado() -> None:
    repo = MagicMock()
    pago = _make_pago()

    resultado = guardar_ingreso(
        pago,
        "MSG-FWD",
        repo,
        moneda="COP",
        correo_origen="alertas@bancolombia.com",
        reenviado=True,
    )

    assert resultado.correo_origen == "alertas@bancolombia.com"
    assert resultado.reenviado is True


def test_guardar_ingreso_llama_repo_guardar() -> None:
    repo = MagicMock()
    pago = _make_pago()

    resultado = guardar_ingreso(pago, "MSG-002", repo, moneda="COP")

    repo.guardar.assert_called_once_with(resultado)


def test_guardar_ingreso_genera_uuid_unico() -> None:
    repo = MagicMock()
    pago = _make_pago()

    r1 = guardar_ingreso(pago, "MSG-A", repo, moneda="COP")
    r2 = guardar_ingreso(pago, "MSG-B", repo, moneda="COP")

    assert r1.id != r2.id


def test_guardar_ingreso_nequi() -> None:
    repo = MagicMock()
    pago = _make_pago(banco_origen="Nequi", monto=Decimal("150000.50"))

    resultado = guardar_ingreso(pago, "MSG-NEQUI", repo, moneda="COP")

    assert resultado.banco == "Nequi"
    assert resultado.monto == Dinero("150000.50", "COP")
