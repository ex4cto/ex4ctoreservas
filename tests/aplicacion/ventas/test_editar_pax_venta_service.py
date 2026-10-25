"""Tests for EditarPaxVentaService — RED first, then GREEN."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import (
    CantidadInvalida,
    LimiteEdicionesAlcanzado,
    MotivoRequerido,
    VentaNoEncontrada,
)


def _make_venta_mock(
    adultos: int = 2,
    ninos: int = 0,
    anulada: bool = False,
    punto_de_venta_id: uuid.UUID | None = None,
) -> MagicMock:
    v = MagicMock()
    v.id = uuid.uuid4()
    v.neto = Dinero(300_000)
    v.valor_venta = Dinero(500_000)
    v.anulada = anulada
    v.tipo_cliente = TipoCliente.EXTERNO
    v.fecha = datetime.date(2026, 9, 1)
    v.adultos = adultos
    v.ninos = ninos
    v.servicio_ids = [uuid.uuid4()]
    v.horarios_por_servicio = None
    participantes = MagicMock()
    participantes.punto_de_venta_id = punto_de_venta_id
    v.participantes = participantes
    return v

def _make_servicio_mock(
    neto_adulto: Decimal = Decimal("80000"),
    neto_nino: Decimal | None = Decimal("40000"),
) -> MagicMock:
    s = MagicMock()
    s.neto_para_horario.return_value = neto_adulto
    s.precio_neto_nino = neto_nino
    return s

def _make_repos(
    venta: MagicMock | None = None,
    servicio: MagicMock | None = None,
    auditoria_records: list[object] | None = None,
    punto: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta

    servicio_repo = MagicMock()
    servicio_repo.buscar_por_id.return_value = servicio

    auditoria_repo = MagicMock()
    auditoria_repo.listar_por_venta_id.return_value = auditoria_records or []

    reglas_repo = MagicMock()
    reglas_repo.buscar_regla.return_value = MagicMock()

    puntos_repo = MagicMock()
    puntos_repo.buscar_por_id.return_value = punto

    comisiones_repo = MagicMock()

    return ventas_repo, servicio_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo

def _make_motor() -> MagicMock:
    motor = MagicMock()
    motor.calcular.return_value = MagicMock()
    return motor

def _make_cmd(
    motivo: str = "error al registrar",
    adultos: int = 3,
    ninos: int = 1,
) -> object:
    from garay.aplicacion.ventas.comandos import EditarPaxVentaComando

    return EditarPaxVentaComando(
        venta_id=uuid.uuid4(),
        adultos=adultos,
        ninos=ninos,
        motivo=motivo,
        realizada_por_telegram_id=123,
        realizada_por_nombre="Admin",
    )

def _make_service(
    ventas: MagicMock,
    servicios: MagicMock,
    auditoria: MagicMock,
    reglas: MagicMock,
    puntos: MagicMock,
    comisiones: MagicMock,
    motor: MagicMock,
) -> object:
    from garay.aplicacion.ventas.editar_pax_venta import EditarPaxVentaService

    return EditarPaxVentaService(
        ventas=ventas,
        servicios=servicios,
        auditoria=auditoria,
        reglas_repo=reglas,
        puntos_repo=puntos,
        comisiones_repo=comisiones,
        motor=motor,
    )

class TestEditarPaxVentaService:
    def test_importable(self) -> None:
        from garay.aplicacion.ventas.editar_pax_venta import EditarPaxVentaService

        assert EditarPaxVentaService is not None

    def test_motivo_vacio_raises(self) -> None:
        ventas, servicios, auditoria, reglas, puntos, comisiones = _make_repos()
        service = _make_service(
            ventas, servicios, auditoria, reglas, puntos, comisiones, _make_motor()
        )
        cmd = _make_cmd(motivo="   ")
        with pytest.raises(MotivoRequerido):
            service.ejecutar(cmd)  # type: ignore[union-attr]

    def test_venta_not_found_raises(self) -> None:
        ventas, servicios, auditoria, reglas, puntos, comisiones = _make_repos(venta=None)
        service = _make_service(
            ventas, servicios, auditoria, reglas, puntos, comisiones, _make_motor()
        )
        cmd = _make_cmd()
        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(cmd)  # type: ignore[union-attr]

    def test_limite_financiero_raises(self) -> None:
        import datetime as dt

        from garay.dominio.ventas.auditoria import AuditoriaVenta

        venta = _make_venta_mock()
        servicio = _make_servicio_mock()
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
        ventas, servicios, auditoria, reglas, puntos, comisiones = _make_repos(
            venta=venta, servicio=servicio, auditoria_records=records
        )
        service = _make_service(
            ventas, servicios, auditoria, reglas, puntos, comisiones, _make_motor()
        )
        cmd = _make_cmd()
        with pytest.raises(LimiteEdicionesAlcanzado):
            service.ejecutar(cmd)  # type: ignore[union-attr]

    def test_happy_path_calls_cambiar_pax(self) -> None:
        venta = _make_venta_mock(adultos=2, ninos=0)
        servicio = _make_servicio_mock()
        ventas, servicios, auditoria, reglas, puntos, comisiones = _make_repos(
            venta=venta, servicio=servicio
        )
        motor = _make_motor()
        service = _make_service(ventas, servicios, auditoria, reglas, puntos, comisiones, motor)
        cmd = _make_cmd(adultos=3, ninos=1)
        service.ejecutar(cmd)  # type: ignore[union-attr]
        venta.cambiar_pax.assert_called_once_with(3, 1)

    def test_happy_path_neto_recalculado_y_guardado(self) -> None:
        """After cambiar_pax, the new neto should be set and the venta persisted."""
        venta = _make_venta_mock(adultos=2, ninos=0)
        servicio = _make_servicio_mock(
            neto_adulto=Decimal("80000"), neto_nino=Decimal("40000")
        )
        ventas, servicios, auditoria, reglas, puntos, comisiones = _make_repos(
            venta=venta, servicio=servicio
        )
        motor = _make_motor()
        service = _make_service(ventas, servicios, auditoria, reglas, puntos, comisiones, motor)
        cmd = _make_cmd(adultos=3, ninos=1)
        service.ejecutar(cmd)  # type: ignore[union-attr]
        # neto = 3*80000 + 1*40000 = 280000
        venta.cambiar_neto.assert_called_once_with(Dinero(Decimal("280000")))
        ventas.guardar.assert_called_once()

    def test_happy_path_audit_first(self) -> None:
        """Audit MUST be persisted before venta and comision."""
        venta = _make_venta_mock()
        servicio = _make_servicio_mock()
        ventas, servicios, auditoria, reglas, puntos, comisiones = _make_repos(
            venta=venta, servicio=servicio
        )
        motor = _make_motor()
        service = _make_service(ventas, servicios, auditoria, reglas, puntos, comisiones, motor)
        call_order: list[str] = []
        auditoria.guardar.side_effect = lambda r: call_order.append("auditoria")
        ventas.guardar.side_effect = lambda v: call_order.append("venta")
        comisiones.guardar.side_effect = lambda c: call_order.append("comision")
        cmd = _make_cmd()
        service.ejecutar(cmd)  # type: ignore[union-attr]
        assert call_order == ["auditoria", "venta", "comision"]

    def test_happy_path_audit_record_has_editar_pax_action(self) -> None:
        venta = _make_venta_mock()
        servicio = _make_servicio_mock()
        ventas, servicios, auditoria, reglas, puntos, comisiones = _make_repos(
            venta=venta, servicio=servicio
        )
        motor = _make_motor()
        service = _make_service(ventas, servicios, auditoria, reglas, puntos, comisiones, motor)
        cmd = _make_cmd()
        service.ejecutar(cmd)  # type: ignore[union-attr]
        saved = auditoria.guardar.call_args[0][0]
        assert saved.accion == AccionAuditoria.EDITAR_PAX

    def test_domain_error_propagated(self) -> None:
        venta = _make_venta_mock()
        venta.cambiar_pax.side_effect = CantidadInvalida("adultos < 1")
        servicio = _make_servicio_mock()
        ventas, servicios, auditoria, reglas, puntos, comisiones = _make_repos(
            venta=venta, servicio=servicio
        )
        service = _make_service(
            ventas, servicios, auditoria, reglas, puntos, comisiones, _make_motor()
        )
        cmd = _make_cmd()
        with pytest.raises(CantidadInvalida):
            service.ejecutar(cmd)  # type: ignore[union-attr]
        auditoria.guardar.assert_not_called()

    def test_motor_calcular_referido_zero(self) -> None:
        venta = _make_venta_mock()
        servicio = _make_servicio_mock()
        ventas, servicios, auditoria, reglas, puntos, comisiones = _make_repos(
            venta=venta, servicio=servicio
        )
        motor = _make_motor()
        service = _make_service(ventas, servicios, auditoria, reglas, puntos, comisiones, motor)
        cmd = _make_cmd()
        service.ejecutar(cmd)  # type: ignore[union-attr]
        args = motor.calcular.call_args[0]
        assert len(args) == 3  # (venta, reglas, punto) — no porcentaje_referido
