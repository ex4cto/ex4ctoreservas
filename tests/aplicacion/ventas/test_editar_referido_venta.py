"""Tests for task 2.2: EditarReferidoVentaService."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.ventas.comandos import EditarReferidoVentaComando
from garay.aplicacion.ventas.editar_referido import EditarReferidoVentaService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.errores import MismoReferido, MotivoRequerido, VentaNoEncontrada
from garay.dominio.ventas.valor_objetos import Participantes


def _make_venta(referido_alias: str | None = None) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(500_000),
        neto=Dinero(400_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 10, 1),
        participantes=Participantes(
            vendedor_nombre="Ana",
            referido_alias=referido_alias,
        ),
    )


def _make_service(
    venta: Venta,
) -> tuple[EditarReferidoVentaService, MagicMock, MagicMock]:
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta
    auditoria_repo = MagicMock()
    auditoria_repo.listar_por_venta.return_value = []
    return (
        EditarReferidoVentaService(ventas=ventas_repo, auditoria=auditoria_repo),
        ventas_repo,
        auditoria_repo,
    )


def _make_cmd(
    venta_id: uuid.UUID,
    nuevo_referido_alias: str | None = "taxi",
    motivo: str = "cliente lo solicitó",
) -> EditarReferidoVentaComando:
    return EditarReferidoVentaComando(
        venta_id=venta_id,
        nuevo_referido_alias=nuevo_referido_alias,
        motivo=motivo,
        realizada_por_telegram_id=5870211102,
        realizada_por_nombre="Ryan",
    )


class TestEditarReferidoVentaService:
    def test_cambia_referido_y_guarda(self) -> None:
        """Task 2.2: service sets referido_alias and saves venta."""
        venta = _make_venta(referido_alias=None)
        service, ventas_repo, _ = _make_service(venta)
        service.ejecutar(_make_cmd(venta.id, nuevo_referido_alias="taxi"))
        assert venta.participantes.referido_alias == "taxi"
        ventas_repo.guardar.assert_called_once_with(venta)

    def test_emite_registro_auditoria(self) -> None:
        """Task 2.2: service emits EDITAR_REFERIDO audit record."""
        venta = _make_venta(referido_alias=None)
        service, _, auditoria_repo = _make_service(venta)
        service.ejecutar(_make_cmd(venta.id))
        auditoria_repo.guardar.assert_called_once()
        registro: AuditoriaVenta = auditoria_repo.guardar.call_args[0][0]
        assert isinstance(registro, AuditoriaVenta)
        assert registro.accion == AccionAuditoria.EDITAR_REFERIDO
        assert registro.venta_id == venta.id

    def test_motivo_vacio_lanza_motivo_requerido(self) -> None:
        venta = _make_venta()
        service, _, _ = _make_service(venta)
        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta.id, motivo="   "))

    def test_venta_no_encontrada_lanza_error(self) -> None:
        venta = _make_venta()
        service, ventas_repo, _ = _make_service(venta)
        ventas_repo.buscar_por_id.return_value = None
        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(_make_cmd(venta.id))

    def test_mismo_referido_propagado(self) -> None:
        """Task 2.2: MismoReferido propagates from domain to caller."""
        venta = _make_venta(referido_alias="taxi")
        service, _, _ = _make_service(venta)
        with pytest.raises(MismoReferido):
            service.ejecutar(_make_cmd(venta.id, nuevo_referido_alias="taxi"))

    def test_datos_previos_incluyen_referido_anterior(self) -> None:
        venta = _make_venta(referido_alias="moto")
        service, _, auditoria_repo = _make_service(venta)
        service.ejecutar(_make_cmd(venta.id, nuevo_referido_alias="taxi"))
        registro: AuditoriaVenta = auditoria_repo.guardar.call_args[0][0]
        assert registro.datos_previos == {"referido_alias": "moto"}
