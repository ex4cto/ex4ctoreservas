"""Tests for EditarNetoVentaService — Phase 2.6.1 RED."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock, call

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import (
    LimiteEdicionesAlcanzado,
    MismoNeto,
    MotivoRequerido,
    NetoIgualOSuperaValorVenta,
    VentaNoEncontrada,
    VentaYaAnulada,
)


def _make_venta_mock(
    neto: Dinero = Dinero(100),
    valor_venta: Dinero = Dinero(300),
    anulada: bool = False,
    punto_de_venta_id: uuid.UUID | None = None,
) -> MagicMock:
    v = MagicMock()
    v.id = uuid.uuid4()
    v.neto = neto
    v.valor_venta = valor_venta
    v.anulada = anulada
    v.tipo_cliente = TipoCliente.EXTERNO
    v.fecha = datetime.date(2026, 9, 1)
    v.adultos = 2
    v.ninos = 0
    participantes = MagicMock()
    participantes.punto_de_venta_id = punto_de_venta_id
    v.participantes = participantes
    return v


def _make_repos(
    venta: MagicMock | None = None,
    auditoria_records: list[object] | None = None,
    punto: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta

    auditoria_repo = MagicMock()
    auditoria_repo.listar_por_venta_id.return_value = auditoria_records or []

    reglas_repo = MagicMock()
    reglas_repo.buscar_regla.return_value = MagicMock()

    puntos_repo = MagicMock()
    puntos_repo.buscar_por_id.return_value = punto

    comisiones_repo = MagicMock()

    return ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo


def _make_motor() -> MagicMock:
    motor = MagicMock()
    motor.calcular.return_value = MagicMock()
    return motor


def _make_cmd(
    motivo: str = "reduccion de costo",
    nuevo_neto: Dinero = Dinero(80),
) -> object:
    from garay.aplicacion.ventas.comandos import EditarNetoVentaComando

    return EditarNetoVentaComando(
        venta_id=uuid.uuid4(),
        nuevo_neto=nuevo_neto,
        motivo=motivo,
        realizada_por_telegram_id=123,
        realizada_por_nombre="Admin",
    )


def _make_service(
    ventas: MagicMock,
    auditoria: MagicMock,
    reglas: MagicMock,
    puntos: MagicMock,
    comisiones: MagicMock,
    motor: MagicMock,
) -> object:
    from garay.aplicacion.ventas.editar_neto import EditarNetoVentaService

    return EditarNetoVentaService(
        ventas=ventas,
        auditoria=auditoria,
        reglas_repo=reglas,
        puntos_repo=puntos,
        comisiones_repo=comisiones,
        motor=motor,
    )


class TestEditarNetoVentaService:
    def test_importable(self) -> None:
        from garay.aplicacion.ventas.editar_neto import EditarNetoVentaService

        assert EditarNetoVentaService is not None

    def test_motivo_vacio_raises(self) -> None:
        ventas, auditoria, reglas, puntos, comisiones = _make_repos()
        service = _make_service(ventas, auditoria, reglas, puntos, comisiones, _make_motor())
        cmd = _make_cmd(motivo="   ")
        with pytest.raises(MotivoRequerido):
            service.ejecutar(cmd)  # type: ignore[union-attr]

    def test_venta_not_found_raises(self) -> None:
        ventas, auditoria, reglas, puntos, comisiones = _make_repos(venta=None)
        service = _make_service(ventas, auditoria, reglas, puntos, comisiones, _make_motor())
        cmd = _make_cmd()
        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(cmd)  # type: ignore[union-attr]

    def test_limite_financiero_raises(self) -> None:
        import datetime as dt

        from garay.dominio.ventas.auditoria import AuditoriaVenta

        venta = _make_venta_mock()
        records = [
            AuditoriaVenta(
                id=uuid.uuid4(),
                venta_id=venta.id,
                accion=AccionAuditoria.EDITAR_CANAL,
                motivo="x",
                realizada_por_telegram_id=1,
                realizada_por_nombre=None,
                realizada_at=dt.datetime.now(dt.UTC),
            )
            for _ in range(3)
        ]
        ventas, auditoria, reglas, puntos, comisiones = _make_repos(
            venta=venta, auditoria_records=records
        )
        service = _make_service(ventas, auditoria, reglas, puntos, comisiones, _make_motor())
        cmd = _make_cmd()
        with pytest.raises(LimiteEdicionesAlcanzado):
            service.ejecutar(cmd)  # type: ignore[union-attr]

    def test_happy_path_calls_cambiar_neto(self) -> None:
        venta = _make_venta_mock()
        ventas, auditoria, reglas, puntos, comisiones = _make_repos(venta=venta)
        motor = _make_motor()
        service = _make_service(ventas, auditoria, reglas, puntos, comisiones, motor)
        cmd = _make_cmd(nuevo_neto=Dinero(80))
        service.ejecutar(cmd)  # type: ignore[union-attr]
        venta.cambiar_neto.assert_called_once_with(Dinero(80))

    def test_happy_path_audit_first(self) -> None:
        """Audit MUST be persisted before venta and comision."""
        venta = _make_venta_mock()
        ventas, auditoria, reglas, puntos, comisiones = _make_repos(venta=venta)
        motor = _make_motor()
        service = _make_service(ventas, auditoria, reglas, puntos, comisiones, motor)
        call_order: list[str] = []
        auditoria.guardar.side_effect = lambda r: call_order.append("auditoria")
        ventas.guardar.side_effect = lambda v: call_order.append("venta")
        comisiones.guardar.side_effect = lambda c: call_order.append("comision")
        cmd = _make_cmd()
        service.ejecutar(cmd)  # type: ignore[union-attr]
        assert call_order == ["auditoria", "venta", "comision"]

    def test_happy_path_audit_record_has_editar_neto(self) -> None:
        venta = _make_venta_mock()
        ventas, auditoria, reglas, puntos, comisiones = _make_repos(venta=venta)
        motor = _make_motor()
        service = _make_service(ventas, auditoria, reglas, puntos, comisiones, motor)
        cmd = _make_cmd()
        service.ejecutar(cmd)  # type: ignore[union-attr]
        saved = auditoria.guardar.call_args[0][0]
        assert saved.accion == AccionAuditoria.EDITAR_NETO

    def test_domain_error_propagated(self) -> None:
        """NetoIgualOSuperaValorVenta raised by domain must propagate to caller."""
        venta = _make_venta_mock()
        venta.cambiar_neto.side_effect = NetoIgualOSuperaValorVenta("blocked")
        ventas, auditoria, reglas, puntos, comisiones = _make_repos(venta=venta)
        service = _make_service(ventas, auditoria, reglas, puntos, comisiones, _make_motor())
        cmd = _make_cmd()
        with pytest.raises(NetoIgualOSuperaValorVenta):
            service.ejecutar(cmd)  # type: ignore[union-attr]
        auditoria.guardar.assert_not_called()

    def test_motor_calcular_called(self) -> None:
        from decimal import Decimal

        venta = _make_venta_mock()
        ventas, auditoria, reglas, puntos, comisiones = _make_repos(venta=venta)
        motor = _make_motor()
        service = _make_service(ventas, auditoria, reglas, puntos, comisiones, motor)
        cmd = _make_cmd()
        service.ejecutar(cmd)  # type: ignore[union-attr]
        motor.calcular.assert_called_once()
        _, kwargs = motor.calcular.call_args
        # porcentaje_referido must be Decimal("0")
        args = motor.calcular.call_args[0]
        assert args[3] == Decimal("0")

    def test_mismo_neto_propagated(self) -> None:
        venta = _make_venta_mock()
        venta.cambiar_neto.side_effect = MismoNeto("idempotent")
        ventas, auditoria, reglas, puntos, comisiones = _make_repos(venta=venta)
        service = _make_service(ventas, auditoria, reglas, puntos, comisiones, _make_motor())
        cmd = _make_cmd()
        with pytest.raises(MismoNeto):
            service.ejecutar(cmd)  # type: ignore[union-attr]

    def test_venta_ya_anulada_propagated(self) -> None:
        venta = _make_venta_mock(anulada=True)
        venta.cambiar_neto.side_effect = VentaYaAnulada("anulada")
        ventas, auditoria, reglas, puntos, comisiones = _make_repos(venta=venta)
        service = _make_service(ventas, auditoria, reglas, puntos, comisiones, _make_motor())
        cmd = _make_cmd()
        with pytest.raises(VentaYaAnulada):
            service.ejecutar(cmd)  # type: ignore[union-attr]
