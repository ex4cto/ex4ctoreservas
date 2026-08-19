"""Tests for guardar_egreso service function — RED phase."""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.webhook.servicio import guardar_egreso
from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.tipos import TipoEgreso
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
    assert resultado.categoria == "otro"
    assert resultado.tipo == TipoEgreso.AUTOMATICO
    assert resultado.referencia == "MSG-EGRESO-001"
    assert resultado.correo_origen is None
    assert resultado.reenviado is False


def test_guardar_egreso_pasa_correo_origen_y_reenviado() -> None:
    repo = MagicMock()
    pago = _make_egreso_extraido()

    resultado = guardar_egreso(
        pago,
        "MSG-EGRESO-FWD",
        repo,
        moneda="COP",
        correo_origen="alertas@bancolombia.com",
        reenviado=True,
    )

    assert resultado.correo_origen == "alertas@bancolombia.com"
    assert resultado.reenviado is True


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


def test_guardar_egreso_categoria_transporte() -> None:
    """Explicit categoria='transporte' must be persisted on the Egreso."""
    repo = MagicMock()
    pago = _make_egreso_extraido(banco_origen="Uber")

    resultado = guardar_egreso(pago, "MSG-UBER-001", repo, moneda="COP", categoria="transporte")

    assert resultado.categoria == "transporte"
    repo.guardar.assert_called_once_with(resultado)


def test_guardar_egreso_categoria_default_es_otro() -> None:
    """Existing callers that omit categoria must still get 'otro' (backward compat)."""
    repo = MagicMock()
    pago = _make_egreso_extraido()

    resultado = guardar_egreso(pago, "MSG-BANCOLOMBIA-001", repo, moneda="COP")

    assert resultado.categoria == "otro"


def test_guardar_egreso_categoria_didi() -> None:
    """categoria='transporte' works for DiDi as well."""
    repo = MagicMock()
    pago = _make_egreso_extraido(banco_origen="DiDi")

    resultado = guardar_egreso(pago, "MSG-DIDI-001", repo, moneda="COP", categoria="transporte")

    assert resultado.categoria == "transporte"


# --- destinatario propagation (REQ-2) ---

class TestGuardarEgresoDestinatario:
    """guardar_egreso propagates destinatario from EgresoExtraido to Egreso (REQ-2)."""

    def test_destinatario_se_propaga_cuando_tiene_valor(self) -> None:
        repo = MagicMock()
        pago = EgresoExtraido(
            monto=Decimal("50000"),
            descripcion="Pago en Rappi",
            banco_origen="Nequi",
            fecha_egreso=datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.UTC),
            destinatario="Rappi",
        )

        resultado = guardar_egreso(pago, "MSG-001", repo, moneda="COP")

        assert resultado.destinatario == "Rappi"

    def test_destinatario_none_se_propaga_como_none(self) -> None:
        repo = MagicMock()
        pago = EgresoExtraido(
            monto=Decimal("3000"),
            descripcion="Pago factura Nequi",
            banco_origen="Nequi",
            fecha_egreso=datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.UTC),
            destinatario=None,
        )

        resultado = guardar_egreso(pago, "MSG-002", repo, moneda="COP")

        assert resultado.destinatario is None
