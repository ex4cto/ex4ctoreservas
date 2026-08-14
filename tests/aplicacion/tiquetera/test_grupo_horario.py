"""Tests for RegistrarVentaService group notification — schedule (horario) line.

RED phase: tests must FAIL before the horario line is implemented in tiquetera/servicio.py.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import cast
from unittest.mock import MagicMock

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.valor_objetos import Participantes

_GRUPO_ID = "grupo-test-horario"
_FECHA = datetime.date(2026, 9, 20)
_UUID_A = uuid.uuid4()


def _build_service(notificador: MagicMock) -> RegistrarVentaService:
    motor = MagicMock()
    motor.calcular.return_value = MagicMock(
        agencia=Dinero(Decimal("50000")),
        vendedor=Dinero(Decimal("25000")),
        cerrador=Dinero(Decimal("25000")),
    )
    reglas_repo = MagicMock()
    reglas_repo.buscar_regla.return_value = MagicMock()
    return RegistrarVentaService(
        ventas=MagicMock(),
        reglas_repo=reglas_repo,
        tiqueteras=MagicMock(),
        puntos_repo=MagicMock(),
        motor=motor,
        notificador=notificador,
        grupo_id=_GRUPO_ID,
        comisiones_repo=MagicMock(),
    )


def _cmd(
    *,
    horarios_por_servicio: dict[uuid.UUID, str] | None,
    servicio_ids: list[uuid.UUID] | None = None,
    servicio_nombres: list[str] | None = None,
) -> RegistrarVentaComando:
    sids = servicio_ids or [_UUID_A]
    nombres = servicio_nombres or ["Islas"]
    return RegistrarVentaComando(
        valor_venta=Dinero(Decimal("500000")),
        neto=Dinero(Decimal("400000")),
        servicio_ids=sids,
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_FECHA,
        participantes=Participantes(
            vendedor_nombre="Ana",
            cerrador_nombre="Ana",
        ),
        adultos=2,
        ninos=0,
        servicio_nombres=nombres,
        horarios_por_servicio=horarios_por_servicio,
    )


def _capture_message(svc: RegistrarVentaService, cmd: RegistrarVentaComando) -> str:
    notificador = cast(MagicMock, svc._notificador)
    svc.ejecutar(cmd)
    return str(notificador.notificar.call_args.args[0])


class TestGrupoHorarioLine:
    def test_single_tour_with_schedule_contains_horario_line(self) -> None:
        """horarios_por_servicio={uuid_A: '07:00'} → message contains '⏰ Horario: 7:00 AM'."""
        notificador = MagicMock()
        svc = _build_service(notificador)
        cmd = _cmd(horarios_por_servicio={_UUID_A: "07:00"})

        msg = _capture_message(svc, cmd)

        assert "⏰ Horario: 7:00 AM" in msg

    def test_horario_line_after_fecha_line(self) -> None:
        """The ⏰ Horario line must appear immediately after the 📅 Fecha line."""
        notificador = MagicMock()
        svc = _build_service(notificador)
        cmd = _cmd(horarios_por_servicio={_UUID_A: "07:00"})

        msg = _capture_message(svc, cmd)

        lines = msg.splitlines()
        fecha_idx = next(i for i, line in enumerate(lines) if "📅 Fecha:" in line)
        horario_idx = next(i for i, line in enumerate(lines) if "⏰ Horario:" in line)
        assert horario_idx == fecha_idx + 1

    def test_no_schedule_no_horario_line(self) -> None:
        """horarios_por_servicio=None → message contains NO '⏰ Horario' (regression guard)."""
        notificador = MagicMock()
        svc = _build_service(notificador)
        cmd = _cmd(horarios_por_servicio=None)

        msg = _capture_message(svc, cmd)

        assert "⏰ Horario" not in msg

    def test_no_schedule_message_byte_identical_to_baseline(self) -> None:
        """Two executions with horarios=None produce identical messages."""
        notificador1 = MagicMock()
        notificador2 = MagicMock()
        svc1 = _build_service(notificador1)
        svc2 = _build_service(notificador2)
        cmd1 = _cmd(horarios_por_servicio=None)
        cmd2 = _cmd(horarios_por_servicio=None)

        msg1 = _capture_message(svc1, cmd1)
        msg2 = _capture_message(svc2, cmd2)

        assert msg1 == msg2

    def test_raw_24h_not_emitted_in_message(self) -> None:
        """Canonical '07:00' must not appear raw in the group message."""
        notificador = MagicMock()
        svc = _build_service(notificador)
        cmd = _cmd(horarios_por_servicio={_UUID_A: "07:00"})

        msg = _capture_message(svc, cmd)

        assert "07:00" not in msg
