"""Tests for EditarEgresoService — RED phase (TDD)."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.egresos.editar_egreso import EditarEgresoService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.auditoria_egreso import AuditoriaEgreso
from garay.dominio.conciliacion.entidades import Egreso
from garay.dominio.conciliacion.errores import EgresoNoEditable
from garay.dominio.conciliacion.tipos import TipoEgreso


def _egreso(tipo: TipoEgreso = TipoEgreso.MANUAL) -> Egreso:
    return Egreso(
        id=uuid.uuid4(),
        descripcion="Concepto original",
        monto=Dinero("50000", "COP"),
        fecha=datetime.date(2026, 7, 1),
        categoria="otro",
        tipo=tipo,
        destinatario="Proveedor A",
    )


def _make_service(egreso: Egreso) -> tuple[EditarEgresoService, MagicMock, MagicMock]:
    egresos = MagicMock()
    egresos.buscar_por_id.return_value = egreso
    auditoria = MagicMock()
    return EditarEgresoService(egresos=egresos, auditoria=auditoria), egresos, auditoria


class TestListarEditables:
    def test_delega_en_listar_manuales(self) -> None:
        egresos = MagicMock()
        egresos.listar_manuales.return_value = ["x", "y"]
        auditoria = MagicMock()
        service = EditarEgresoService(egresos=egresos, auditoria=auditoria)
        assert service.listar_editables(limite=5) == ["x", "y"]
        egresos.listar_manuales.assert_called_once_with(5)


class TestEditarCampos:
    def test_editar_categoria_actualiza_y_audita(self) -> None:
        egreso = _egreso()
        service, egresos, auditoria = _make_service(egreso)
        actualizado = service.editar_categoria(
            egreso.id, "transporte", por_telegram_id=9, por_nombre="Garay"
        )
        assert actualizado.categoria == "transporte"
        egresos.guardar.assert_called_once()
        registro = auditoria.guardar.call_args[0][0]
        assert isinstance(registro, AuditoriaEgreso)
        assert registro.campo == "categoria"
        assert registro.valor_anterior == "otro"
        assert registro.valor_nuevo == "transporte"
        assert registro.realizada_por_telegram_id == 9
        assert registro.realizada_por_nombre == "Garay"
        assert registro.egreso_id == egreso.id

    def test_editar_monto_preserva_moneda_y_audita(self) -> None:
        egreso = _egreso()
        service, _egresos, auditoria = _make_service(egreso)
        actualizado = service.editar_monto(
            egreso.id, Decimal("75000"), por_telegram_id=1, por_nombre=None
        )
        assert actualizado.monto == Dinero("75000", "COP")
        registro = auditoria.guardar.call_args[0][0]
        assert registro.campo == "monto"
        assert registro.valor_anterior == "50000.00"
        assert registro.valor_nuevo == "75000.00"

    def test_editar_fecha(self) -> None:
        egreso = _egreso()
        service, _, auditoria = _make_service(egreso)
        actualizado = service.editar_fecha(
            egreso.id, datetime.date(2026, 8, 15), por_telegram_id=1, por_nombre="A"
        )
        assert actualizado.fecha == datetime.date(2026, 8, 15)
        assert auditoria.guardar.call_args[0][0].campo == "fecha"

    def test_editar_concepto(self) -> None:
        egreso = _egreso()
        service, _, auditoria = _make_service(egreso)
        actualizado = service.editar_concepto(
            egreso.id, "Nuevo concepto", por_telegram_id=1, por_nombre="A"
        )
        assert actualizado.descripcion == "Nuevo concepto"
        assert auditoria.guardar.call_args[0][0].campo == "concepto"

    def test_editar_destinatario(self) -> None:
        egreso = _egreso()
        service, _, auditoria = _make_service(egreso)
        actualizado = service.editar_destinatario(
            egreso.id, "Proveedor B", por_telegram_id=1, por_nombre="A"
        )
        assert actualizado.destinatario == "Proveedor B"
        assert auditoria.guardar.call_args[0][0].campo == "destinatario"


class TestSoloManuales:
    def test_editar_egreso_automatico_lanza_y_no_guarda(self) -> None:
        egreso = _egreso(tipo=TipoEgreso.AUTOMATICO)
        service, egresos, auditoria = _make_service(egreso)
        with pytest.raises(EgresoNoEditable):
            service.editar_categoria(egreso.id, "otro", por_telegram_id=1, por_nombre="A")
        egresos.guardar.assert_not_called()
        auditoria.guardar.assert_not_called()

    def test_editar_egreso_inexistente_lanza_value_error(self) -> None:
        egresos = MagicMock()
        egresos.buscar_por_id.return_value = None
        auditoria = MagicMock()
        service = EditarEgresoService(egresos=egresos, auditoria=auditoria)
        with pytest.raises(ValueError):
            service.editar_categoria(
                uuid.uuid4(), "otro", por_telegram_id=1, por_nombre="A"
            )
