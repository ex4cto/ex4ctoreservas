"""Tests for EditarParticipantesVentaService — Strict TDD."""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from unittest.mock import MagicMock, call

import pytest

from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import (
    LimiteEdicionesAlcanzado,
    MotivoRequerido,
    VentaNoEncontrada,
    VentaYaAnulada,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_venta_mock(
    vendedor_id: uuid.UUID | None = None,
    vendedor_nombre: str | None = "Ana",
    cerrador_id: uuid.UUID | None = None,
    cerrador_nombre: str | None = "Luis",
    anulada: bool = False,
    punto_de_venta_id: uuid.UUID | None = None,
    adultos: int = 2,
    ninos: int = 0,
) -> MagicMock:
    from garay.dominio.ventas.errores import MismosParticipantes

    v = MagicMock()
    v.id = uuid.uuid4()
    v.anulada = anulada
    v.adultos = adultos
    v.ninos = ninos
    v.fecha = datetime.date(2026, 9, 1)

    participantes = MagicMock()
    participantes.vendedor_id = vendedor_id or uuid.uuid4()
    participantes.vendedor_nombre = vendedor_nombre
    participantes.cerrador_id = cerrador_id or uuid.uuid4()
    participantes.cerrador_nombre = cerrador_nombre
    participantes.punto_de_venta_id = punto_de_venta_id
    v.participantes = participantes

    def _cambiar_participantes(
        nuevo_vendedor_id: uuid.UUID | None,
        nuevo_vendedor_nombre: str | None,
        nuevo_cerrador_id: uuid.UUID | None,
        nuevo_cerrador_nombre: str | None,
    ) -> None:
        if v.anulada:
            raise VentaYaAnulada("Ya anulada.")
        if (
            nuevo_vendedor_id == v.participantes.vendedor_id
            and nuevo_vendedor_nombre == v.participantes.vendedor_nombre
            and nuevo_cerrador_id == v.participantes.cerrador_id
            and nuevo_cerrador_nombre == v.participantes.cerrador_nombre
        ):
            raise MismosParticipantes("Mismos participantes.")
        v.participantes.vendedor_id = nuevo_vendedor_id
        v.participantes.vendedor_nombre = nuevo_vendedor_nombre
        v.participantes.cerrador_id = nuevo_cerrador_id
        v.participantes.cerrador_nombre = nuevo_cerrador_nombre

    v.cambiar_participantes.side_effect = _cambiar_participantes
    return v


def _make_repos(
    venta: MagicMock | None = None,
    auditoria_records: list[MagicMock] | None = None,
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
    venta_id: uuid.UUID | None = None,
    nuevo_vendedor_id: uuid.UUID | None = None,
    nuevo_vendedor_nombre: str | None = "Pedro",
    nuevo_cerrador_id: uuid.UUID | None = None,
    nuevo_cerrador_nombre: str | None = "Luis",
    motivo: str = "Corrección de participante",
) -> object:
    from garay.aplicacion.ventas.comandos import EditarParticipantesVentaComando

    return EditarParticipantesVentaComando(
        venta_id=venta_id or uuid.uuid4(),
        nuevo_vendedor_id=nuevo_vendedor_id or uuid.uuid4(),
        nuevo_vendedor_nombre=nuevo_vendedor_nombre,
        nuevo_cerrador_id=nuevo_cerrador_id or uuid.uuid4(),
        nuevo_cerrador_nombre=nuevo_cerrador_nombre,
        motivo=motivo,
        realizada_por_telegram_id=42,
        realizada_por_nombre="Admin",
    )


def _make_service(
    ventas_repo: MagicMock,
    auditoria_repo: MagicMock,
    reglas_repo: MagicMock,
    puntos_repo: MagicMock,
    comisiones_repo: MagicMock,
    motor: MagicMock | None = None,
) -> object:
    from garay.aplicacion.ventas.editar_participantes import EditarParticipantesVentaService

    return EditarParticipantesVentaService(
        ventas=ventas_repo,
        auditoria=auditoria_repo,
        reglas_repo=reglas_repo,
        puntos_repo=puntos_repo,
        comisiones_repo=comisiones_repo,
        motor=motor or _make_motor(),
    )


def _rec(accion: AccionAuditoria) -> MagicMock:
    r = MagicMock()
    r.accion = accion
    return r


# ---------------------------------------------------------------------------
# EditarParticipantesVentaComando shape
# ---------------------------------------------------------------------------


class TestEditarParticipantesVentaComando:
    def test_comando_is_importable(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarParticipantesVentaComando

        assert EditarParticipantesVentaComando is not None

    def test_comando_is_frozen_dataclass(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarParticipantesVentaComando

        fields = {f.name for f in dataclasses.fields(EditarParticipantesVentaComando)}
        assert fields == {
            "venta_id",
            "nuevo_vendedor_id",
            "nuevo_vendedor_nombre",
            "nuevo_cerrador_id",
            "nuevo_cerrador_nombre",
            "motivo",
            "realizada_por_telegram_id",
            "realizada_por_nombre",
        }

    def test_comando_is_immutable(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarParticipantesVentaComando

        cmd = EditarParticipantesVentaComando(
            venta_id=uuid.uuid4(),
            nuevo_vendedor_id=uuid.uuid4(),
            nuevo_vendedor_nombre="Pedro",
            nuevo_cerrador_id=uuid.uuid4(),
            nuevo_cerrador_nombre="Luis",
            motivo="test",
            realizada_por_telegram_id=1,
            realizada_por_nombre="Admin",
        )
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            cmd.motivo = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EDITAR_PARTICIPANTES in ACCIONES_EDICION
# ---------------------------------------------------------------------------


class TestAccionesEdicionIncludeEditarParticipantes:
    def test_editar_participantes_in_acciones_edicion(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import ACCIONES_EDICION
        from garay.dominio.ventas.auditoria import AccionAuditoria

        assert AccionAuditoria.EDITAR_PARTICIPANTES in ACCIONES_EDICION


# ---------------------------------------------------------------------------
# EditarParticipantesVentaService — all scenarios
# ---------------------------------------------------------------------------


class TestEditarParticipantesVentaService:
    def test_motivo_vacio_raises_motivo_requerido(self) -> None:
        venta = _make_venta_mock()
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta_id=venta.id, motivo="   "))

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_venta_no_encontrada_raises(self) -> None:
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta=None)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(_make_cmd())

        ventas_repo.guardar.assert_not_called()

    def test_limite_ediciones_raises(self) -> None:
        venta = _make_venta_mock()
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(
            venta,
            auditoria_records=[
                _rec(AccionAuditoria.EDITAR_FECHA),
                _rec(AccionAuditoria.EDITAR_FECHA),
            ],
        )
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        with pytest.raises(LimiteEdicionesAlcanzado):
            service.ejecutar(_make_cmd(venta_id=venta.id))

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_mismos_participantes_raises(self) -> None:
        from garay.dominio.ventas.errores import MismosParticipantes

        venta = _make_venta_mock()
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        cmd = _make_cmd(
            venta_id=venta.id,
            nuevo_vendedor_id=venta.participantes.vendedor_id,
            nuevo_vendedor_nombre=venta.participantes.vendedor_nombre,
            nuevo_cerrador_id=venta.participantes.cerrador_id,
            nuevo_cerrador_nombre=venta.participantes.cerrador_nombre,
        )

        with pytest.raises(MismosParticipantes):
            service.ejecutar(cmd)

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_venta_ya_anulada_raises(self) -> None:
        venta = _make_venta_mock(anulada=True)
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        with pytest.raises(VentaYaAnulada):
            service.ejecutar(_make_cmd(venta_id=venta.id))

        ventas_repo.guardar.assert_not_called()

    def test_cambia_vendedor_exitosamente(self) -> None:
        venta = _make_venta_mock()
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        nuevo_id = uuid.uuid4()
        cmd = _make_cmd(
            venta_id=venta.id,
            nuevo_vendedor_id=nuevo_id,
            nuevo_vendedor_nombre="Pedro",
            nuevo_cerrador_id=venta.participantes.cerrador_id,
            nuevo_cerrador_nombre=venta.participantes.cerrador_nombre,
        )

        service.ejecutar(cmd)

        venta.cambiar_participantes.assert_called_once()
        ventas_repo.guardar.assert_called_once_with(venta)
        auditoria_repo.guardar.assert_called_once()

    def test_cambia_cerrador_exitosamente(self) -> None:
        venta = _make_venta_mock()
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        nuevo_id = uuid.uuid4()
        cmd = _make_cmd(
            venta_id=venta.id,
            nuevo_vendedor_id=venta.participantes.vendedor_id,
            nuevo_vendedor_nombre=venta.participantes.vendedor_nombre,
            nuevo_cerrador_id=nuevo_id,
            nuevo_cerrador_nombre="Carlos",
        )

        service.ejecutar(cmd)

        venta.cambiar_participantes.assert_called_once()
        ventas_repo.guardar.assert_called_once_with(venta)
        auditoria_repo.guardar.assert_called_once()

    def test_guarda_en_orden_audit_first(self) -> None:
        """auditoria.guardar MUST be called before ventas.guardar and comisiones.guardar."""
        venta = _make_venta_mock()
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        motor = _make_motor()

        call_order: list[str] = []
        auditoria_repo.guardar.side_effect = lambda _: call_order.append("auditoria")
        ventas_repo.guardar.side_effect = lambda _: call_order.append("ventas")
        comisiones_repo.guardar.side_effect = lambda _: call_order.append("comisiones")

        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo, motor)

        nuevo_id = uuid.uuid4()
        cmd = _make_cmd(
            venta_id=venta.id,
            nuevo_vendedor_id=nuevo_id,
            nuevo_vendedor_nombre="Pedro",
            nuevo_cerrador_id=venta.participantes.cerrador_id,
            nuevo_cerrador_nombre=venta.participantes.cerrador_nombre,
        )
        service.ejecutar(cmd)

        assert call_order == ["auditoria", "ventas", "comisiones"]

    def test_auditoria_tiene_accion_editar_participantes(self) -> None:
        venta = _make_venta_mock()
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        nuevo_id = uuid.uuid4()
        cmd = _make_cmd(
            venta_id=venta.id,
            nuevo_vendedor_id=nuevo_id,
            nuevo_vendedor_nombre="Pedro",
            nuevo_cerrador_id=venta.participantes.cerrador_id,
            nuevo_cerrador_nombre=venta.participantes.cerrador_nombre,
        )
        service.ejecutar(cmd)

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.accion == AccionAuditoria.EDITAR_PARTICIPANTES
