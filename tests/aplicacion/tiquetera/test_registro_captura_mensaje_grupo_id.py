"""Tests for Phase 1.4: RegistrarVentaService captures mensaje_grupo_id.

TDD RED: written first; fails until RegistrarVentaService captures the
return value of notificador.notificar() and persists it on the venta.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, call

import pytest

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.valor_objetos import Participantes

_GRUPO_ID = "grupo-captura-test"
_MSG_ID = 999_888


def _build_service(
    *,
    ventas: MagicMock,
    notificador: MagicMock,
) -> RegistrarVentaService:
    return RegistrarVentaService(
        ventas=ventas,
        reglas_repo=MagicMock(),
        tiqueteras=MagicMock(),
        puntos_repo=MagicMock(),
        motor=MagicMock(),
        notificador=notificador,
        grupo_id=_GRUPO_ID,
        comisiones_repo=MagicMock(),
        socios_config=MagicMock(),
    )


def _cmd() -> RegistrarVentaComando:
    return RegistrarVentaComando(
        valor_venta=Dinero(300_000),
        neto=Dinero(100_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 12, 1),
        participantes=Participantes(
            vendedor_nombre="Vendedor",
            cerrador_nombre=None,
            punto_de_venta_id=None,
        ),
        adultos=1,
        ninos=0,
        foto_referencia=None,
        porcentaje_referido=Decimal("0"),
        abono=None,
        cliente_nombre="Test Cliente",
        cliente_telefono=None,
        cliente_email=None,
        servicio_nombres=["Tour Test"],
        hotel=None,
        habitacion=None,
    )


class TestRegistroCapturaMensajeGrupoId:
    def test_mensaje_grupo_id_persisted_when_notificador_returns_id(self) -> None:
        """When notificador.notificar() returns an int, venta.mensaje_grupo_id is
        persisted via ventas.guardar() after the notification call."""
        ventas = MagicMock()
        notificador = MagicMock()
        notificador.notificar.return_value = _MSG_ID

        service = _build_service(ventas=ventas, notificador=notificador)
        service.ejecutar(_cmd())

        # ventas.guardar must have been called at least twice:
        # once for the initial persist and once after capturing mensaje_grupo_id.
        assert ventas.guardar.call_count >= 2

        # The last call to ventas.guardar must pass a Venta with mensaje_grupo_id set.
        last_venta = ventas.guardar.call_args_list[-1][0][0]
        assert last_venta.mensaje_grupo_id == _MSG_ID

    def test_mensaje_grupo_id_none_when_notificador_returns_none(self) -> None:
        """When notificador.notificar() returns None (notification failed best-effort),
        the venta.mensaje_grupo_id remains None — no extra guardar needed."""
        ventas = MagicMock()
        notificador = MagicMock()
        notificador.notificar.return_value = None

        service = _build_service(ventas=ventas, notificador=notificador)
        service.ejecutar(_cmd())

        # When return value is None, no extra guardar call should be made for
        # mensaje_grupo_id (nothing to persist).
        # The first guardar persists the venta; if a second guardar happens,
        # it must not set a non-None mensaje_grupo_id.
        for call_args in ventas.guardar.call_args_list:
            venta = call_args[0][0]
            # None is acceptable; a non-None value would be wrong here
            assert venta.mensaje_grupo_id is None

    def test_venta_still_saved_when_notificador_raises(self) -> None:
        """Notification exceptions are swallowed; the venta remains committed."""
        ventas = MagicMock()
        notificador = MagicMock()
        notificador.notificar.side_effect = Exception("Telegram down")

        service = _build_service(ventas=ventas, notificador=notificador)
        # Must not raise
        service.ejecutar(_cmd())

        # Initial persist must still have happened
        assert ventas.guardar.call_count >= 1
