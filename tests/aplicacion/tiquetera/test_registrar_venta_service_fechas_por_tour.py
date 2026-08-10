"""Tests for RegistrarVentaService with per-tour dates (Slice 2 — fecha-por-tour)."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.valor_objetos import Participantes

_GRUPO_ID = "grupo-test-123"
_VALOR_VENTA = Dinero(1_000_000)
_NETO = Dinero(900_000)
_S1_ID = uuid.uuid4()
_S2_ID = uuid.uuid4()
_CLIENTE_ID = uuid.uuid4()
_FECHA = datetime.date(2026, 12, 20)


def _build_service(
    ventas: MagicMock | None = None,
    motor: MagicMock | None = None,
) -> RegistrarVentaService:
    m = motor or MagicMock()
    m.calcular.return_value = MagicMock()
    return RegistrarVentaService(
        ventas=ventas or MagicMock(),
        reglas_repo=MagicMock(),
        tiqueteras=MagicMock(),
        puntos_repo=MagicMock(),
        motor=m,
        notificador=MagicMock(),
        grupo_id=_GRUPO_ID,
        comisiones_repo=MagicMock(),
    )


def _cmd_con_fechas(
    fechas_por_servicio: dict[uuid.UUID, datetime.datetime] | None,
) -> RegistrarVentaComando:
    return RegistrarVentaComando(
        valor_venta=_VALOR_VENTA,
        neto=_NETO,
        servicio_ids=[_S1_ID, _S2_ID],
        cliente_id=_CLIENTE_ID,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_FECHA,
        participantes=Participantes(vendedor_nombre="Ana", cerrador_nombre="Luis"),
        adultos=2,
        ninos=0,
        fechas_por_servicio=fechas_por_servicio,
    )


class TestRegistrarVentaConFechasPorServicio:
    def test_fechas_por_servicio_persisted_on_venta(self) -> None:
        """When command has fechas_por_servicio, venta.fechas_por_servicio is set."""
        dt1 = datetime.datetime(2026, 12, 20, 10, 0)
        dt2 = datetime.datetime(2026, 12, 22, 9, 0)
        fechas = {_S1_ID: dt1, _S2_ID: dt2}

        ventas = MagicMock()
        service = _build_service(ventas=ventas)
        service.ejecutar(_cmd_con_fechas(fechas))

        ventas.guardar.assert_called_once()
        venta = ventas.guardar.call_args[0][0]
        assert venta.fechas_por_servicio == fechas

    def test_venta_fecha_equals_primary_passed_in_cmd(self) -> None:
        """venta.fecha equals cmd.fecha (primary date, derived before service call)."""
        dt1 = datetime.datetime(2026, 12, 20, 10, 0)
        dt2 = datetime.datetime(2026, 12, 22, 9, 0)
        fechas = {_S1_ID: dt1, _S2_ID: dt2}

        ventas = MagicMock()
        service = _build_service(ventas=ventas)
        service.ejecutar(_cmd_con_fechas(fechas))

        venta = ventas.guardar.call_args[0][0]
        assert venta.fecha == _FECHA  # = 2026-12-20, the primary date passed in

    def test_fechas_por_servicio_none_when_not_provided(self) -> None:
        """When fechas_por_servicio is None, venta.fechas_por_servicio is None."""
        ventas = MagicMock()
        service = _build_service(ventas=ventas)
        service.ejecutar(_cmd_con_fechas(None))

        venta = ventas.guardar.call_args[0][0]
        assert venta.fechas_por_servicio is None

    def test_comision_fecha_equals_venta_fecha(self) -> None:
        """ComisionRegistrada.fecha == venta.fecha (primary date)."""
        dt1 = datetime.datetime(2026, 12, 20, 10, 0)
        dt2 = datetime.datetime(2026, 12, 22, 9, 0)
        fechas = {_S1_ID: dt1, _S2_ID: dt2}

        comisiones_repo = MagicMock()
        service = RegistrarVentaService(
            ventas=MagicMock(),
            reglas_repo=MagicMock(),
            tiqueteras=MagicMock(),
            puntos_repo=MagicMock(),
            motor=MagicMock(calcular=MagicMock(return_value=MagicMock())),
            notificador=MagicMock(),
            grupo_id=_GRUPO_ID,
            comisiones_repo=comisiones_repo,
        )
        service.ejecutar(_cmd_con_fechas(fechas))

        comisiones_repo.guardar.assert_called_once()
        comision = comisiones_repo.guardar.call_args[0][0]
        assert comision.fecha == _FECHA


class TestNotificacionGrupoFechasPorServicio:
    """Group-notification date rendering (Slice 3 — display)."""

    def _cmd(
        self,
        fechas_por_servicio: dict[uuid.UUID, datetime.datetime] | None,
        servicio_ids: list[uuid.UUID],
        servicio_nombres: list[str],
    ) -> RegistrarVentaComando:
        return RegistrarVentaComando(
            valor_venta=_VALOR_VENTA,
            neto=_NETO,
            servicio_ids=servicio_ids,
            cliente_id=_CLIENTE_ID,
            tipo_cliente=TipoCliente.EXTERNO,
            fecha=_FECHA,
            participantes=Participantes(vendedor_nombre="Ana", cerrador_nombre="Luis"),
            adultos=2,
            ninos=0,
            servicio_nombres=servicio_nombres,
            fechas_por_servicio=fechas_por_servicio,
        )

    def _mensaje_notificado(self, cmd: RegistrarVentaComando) -> str:
        notificador = MagicMock()
        service = _build_service()
        service._notificador = notificador
        service.ejecutar(cmd)
        notificador.notificar.assert_called_once()
        mensaje: str = notificador.notificar.call_args[0][0]
        return mensaje

    def test_single_tour_date_line_unchanged(self) -> None:
        """One tour → '📅 Fecha: DD/MM/YYYY' (byte-identical parity)."""
        cmd = self._cmd(
            fechas_por_servicio=None,
            servicio_ids=[_S1_ID],
            servicio_nombres=["Islas del Rosario"],
        )
        mensaje = self._mensaje_notificado(cmd)
        assert "📅 Fecha: 20/12/2026" in mensaje
        assert "Islas del Rosario 20/12" not in mensaje

    def test_two_tours_compact_date_line(self) -> None:
        """Two tours → compact 'nombre DD/MM HH:MM, ...' after the 📅 prefix."""
        dt1 = datetime.datetime(2026, 12, 20, 8, 0)
        dt2 = datetime.datetime(2026, 12, 22, 19, 0)
        cmd = self._cmd(
            fechas_por_servicio={_S1_ID: dt1, _S2_ID: dt2},
            servicio_ids=[_S1_ID, _S2_ID],
            servicio_nombres=["Islas del Rosario", "Bahía Rumbera"],
        )
        mensaje = self._mensaje_notificado(cmd)
        assert (
            "📅 Fecha: Islas del Rosario 20/12 08:00, Bahía Rumbera 22/12 19:00"
            in mensaje
        )

    def test_three_tours_compact_date_line_in_order(self) -> None:
        """Three tours render in servicio_ids order after the prefix."""
        s3 = uuid.uuid4()
        dt1 = datetime.datetime(2026, 12, 20, 8, 0)
        dt2 = datetime.datetime(2026, 12, 22, 19, 0)
        dt3 = datetime.datetime(2026, 12, 18, 6, 30)
        cmd = self._cmd(
            fechas_por_servicio={_S1_ID: dt1, _S2_ID: dt2, s3: dt3},
            servicio_ids=[_S1_ID, _S2_ID, s3],
            servicio_nombres=["Islas del Rosario", "Bahía Rumbera", "City Tour"],
        )
        mensaje = self._mensaje_notificado(cmd)
        assert (
            "📅 Fecha: Islas del Rosario 20/12 08:00, "
            "Bahía Rumbera 22/12 19:00, City Tour 18/12 06:30" in mensaje
        )

    def test_two_tours_empty_fechas_dict_degrades_to_scalar(self) -> None:
        """Two tours with fechas_por_servicio={} must degrade to scalar DD/MM/YYYY,
        not render '00:00' midnight artifacts from a dict-miss fallback."""
        cmd = self._cmd(
            fechas_por_servicio={},
            servicio_ids=[_S1_ID, _S2_ID],
            servicio_nombres=["Islas del Rosario", "Bahía Rumbera"],
        )
        mensaje = self._mensaje_notificado(cmd)
        assert "📅 Fecha: 20/12/2026" in mensaje
        assert "00:00" not in mensaje
