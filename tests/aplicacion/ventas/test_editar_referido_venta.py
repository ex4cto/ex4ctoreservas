"""Tests for task 2.2: EditarReferidoVentaService."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.ventas.comandos import EditarReferidoVentaComando
from garay.aplicacion.ventas.editar_referido import EditarReferidoVentaService
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.motor import MotorComisiones
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.auditoria import AccionAuditoria, AuditoriaVenta
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.errores import (
    MismoReferido,
    MotivoRequerido,
    PermisoDenegado,
    VentaNoEncontrada,
)
from garay.dominio.ventas.valor_objetos import Participantes


def _make_snapshot() -> SnapshotReglas:
    return SnapshotReglas(
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("15"),
        porcentaje_cerrador=Decimal("15"),
        porcentaje_capa_punto=Decimal("0"),
    )


def _make_desglose(referido: int = 0) -> DesgloseComision:
    return DesgloseComision(
        vendedor=Dinero(90_000),
        cerrador=Dinero(90_000),
        punto_de_venta=Dinero(0),
        referido=Dinero(referido),
        agencia=Dinero(420_000),
        snapshot=_make_snapshot(),
        neto_vendedor=Dinero(90_000 - referido // 2),
        neto_cerrador=Dinero(90_000 - referido // 2),
    )


def _make_venta(referido_alias: str | None = None) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(700_000),
        neto=Dinero(600_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 10, 1),
        participantes=Participantes(
            vendedor_nombre="Ana",
            cerrador_nombre="Bob",
            referido_alias=referido_alias,
        ),
    )


def _make_service(
    venta: Venta,
) -> tuple[EditarReferidoVentaService, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta
    auditoria_repo = MagicMock()
    auditoria_repo.listar_por_venta.return_value = []
    auditoria_repo.listar_por_venta_id.return_value = []
    reglas_repo = MagicMock()
    reglas_repo.buscar_regla.return_value = MagicMock()
    puntos_repo = MagicMock()
    puntos_repo.buscar_por_id.return_value = None
    comisiones_repo = MagicMock()
    motor = MagicMock(spec=MotorComisiones)
    motor.calcular.return_value = _make_desglose(referido=18_000)
    return (
        EditarReferidoVentaService(
            ventas=ventas_repo,
            auditoria=auditoria_repo,
            reglas_repo=reglas_repo,
            puntos_repo=puntos_repo,
            comisiones_repo=comisiones_repo,
            motor=motor,
        ),
        ventas_repo,
        auditoria_repo,
        reglas_repo,
        puntos_repo,
        comisiones_repo,
        motor,
    )


def _make_cmd(
    venta_id: uuid.UUID,
    nuevo_referido_alias: str | None = "taxi",
    motivo: str = "cliente lo solicitó",
    telegram_id: int = 5870211102,
) -> EditarReferidoVentaComando:
    return EditarReferidoVentaComando(
        venta_id=venta_id,
        nuevo_referido_alias=nuevo_referido_alias,
        motivo=motivo,
        realizada_por_telegram_id=telegram_id,
        realizada_por_nombre="Ryan",
    )


class TestEditarReferidoVentaService:
    def test_cambia_referido_y_guarda(self) -> None:
        """Task 2.2: service sets referido_alias and saves venta."""
        venta = _make_venta(referido_alias=None)
        service, ventas_repo, *_ = _make_service(venta)
        service.ejecutar(_make_cmd(venta.id, nuevo_referido_alias="taxi"))
        assert venta.participantes.referido_alias == "taxi"
        ventas_repo.guardar.assert_called_once_with(venta)

    def test_emite_registro_auditoria(self) -> None:
        """Task 2.2: service emits EDITAR_REFERIDO audit record."""
        venta = _make_venta(referido_alias=None)
        service, _, auditoria_repo, *_ = _make_service(venta)
        service.ejecutar(_make_cmd(venta.id))
        auditoria_repo.guardar.assert_called_once()
        registro: AuditoriaVenta = auditoria_repo.guardar.call_args[0][0]
        assert isinstance(registro, AuditoriaVenta)
        assert registro.accion == AccionAuditoria.EDITAR_REFERIDO
        assert registro.venta_id == venta.id

    def test_motivo_vacio_lanza_motivo_requerido(self) -> None:
        venta = _make_venta()
        service, *_ = _make_service(venta)
        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta.id, motivo="   "))

    def test_venta_no_encontrada_lanza_error(self) -> None:
        venta = _make_venta()
        service, ventas_repo, *_ = _make_service(venta)
        ventas_repo.buscar_por_id.return_value = None
        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(_make_cmd(venta.id))

    def test_mismo_referido_propagado(self) -> None:
        """Task 2.2: MismoReferido propagates from domain to caller."""
        venta = _make_venta(referido_alias="taxi")
        service, *_ = _make_service(venta)
        with pytest.raises(MismoReferido):
            service.ejecutar(_make_cmd(venta.id, nuevo_referido_alias="taxi"))

    def test_datos_previos_incluyen_referido_anterior(self) -> None:
        venta = _make_venta(referido_alias="moto")
        service, _, auditoria_repo, *_ = _make_service(venta)
        service.ejecutar(_make_cmd(venta.id, nuevo_referido_alias="taxi"))
        registro: AuditoriaVenta = auditoria_repo.guardar.call_args[0][0]
        assert registro.datos_previos == {"referido_alias": "moto"}

    def test_no_admin_lanza_permiso_denegado(self) -> None:
        """Spec §4: non-admin telegram_id must be rejected before any state change."""
        venta = _make_venta(referido_alias=None)
        service, ventas_repo, auditoria_repo, *_ = _make_service(venta)
        with pytest.raises(PermisoDenegado):
            service.ejecutar(_make_cmd(venta.id, telegram_id=9999999999))
        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_admin_sharimel_puede_editar(self) -> None:
        """Spec §4: Sharimel (8710698734) is an authorized admin."""
        venta = _make_venta(referido_alias=None)
        service, ventas_repo, *_ = _make_service(venta)
        service.ejecutar(_make_cmd(venta.id, telegram_id=8710698734))
        ventas_repo.guardar.assert_called_once()

    def test_admin_garay_puede_editar(self) -> None:
        """Spec §4: Garay (1379898979) is an authorized admin."""
        venta = _make_venta(referido_alias=None)
        service, ventas_repo, *_ = _make_service(venta)
        service.ejecutar(_make_cmd(venta.id, telegram_id=1379898979))
        ventas_repo.guardar.assert_called_once()

    def test_recomputa_comision_y_persiste_snapshot(self) -> None:
        """Spec §4: service must recompute commission and persist ComisionRegistrada."""
        venta = _make_venta(referido_alias=None)
        service, _, _, _, _, comisiones_repo, motor = _make_service(venta)
        service.ejecutar(_make_cmd(venta.id, nuevo_referido_alias="taxi"))
        motor.calcular.assert_called_once()
        comisiones_repo.guardar.assert_called_once()
        saved: ComisionRegistrada = comisiones_repo.guardar.call_args[0][0]
        assert isinstance(saved, ComisionRegistrada)
        assert saved.venta_id == venta.id
