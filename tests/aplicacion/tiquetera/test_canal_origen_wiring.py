"""TDD RED — WU-4: canal_origen wired through command, service notification, and handler."""

from __future__ import annotations

import datetime
import uuid
from typing import Any
from unittest.mock import MagicMock

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.valor_objetos import Participantes

_VALOR = Dinero(500_000)
_NETO = Dinero(400_000)
_SERVICIO_ID = uuid.uuid4()
_CLIENTE_ID = uuid.uuid4()
_FECHA = datetime.date(2026, 7, 1)


def _build_service(**kwargs: object) -> RegistrarVentaService:
    defaults: dict[str, Any] = dict(
        ventas=MagicMock(),
        reglas_repo=MagicMock(),
        tiqueteras=MagicMock(),
        puntos_repo=MagicMock(),
        motor=MagicMock(),
        notificador=MagicMock(),
        grupo_id="grupo-test",
        comisiones_repo=MagicMock(),
    )
    defaults.update(kwargs)
    return RegistrarVentaService(**defaults)


def _cmd(**kwargs: object) -> RegistrarVentaComando:
    defaults: dict[str, Any] = dict(
        valor_venta=_VALOR,
        neto=_NETO,
        servicio_ids=[_SERVICIO_ID],
        cliente_id=_CLIENTE_ID,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_FECHA,
        participantes=Participantes(),
        adultos=1,
        ninos=0,
    )
    defaults.update(kwargs)
    return RegistrarVentaComando(**defaults)


class TestRegistrarVentaComandoCanalOrigen:
    def test_comando_acepta_canal_origen(self) -> None:
        cmd = _cmd(canal_origen="WhatsApp")
        assert cmd.canal_origen == "WhatsApp"

    def test_comando_canal_default_none(self) -> None:
        cmd = _cmd()
        assert cmd.canal_origen is None


class TestRegistrarVentaServiceCanalOrigen:
    def test_servicio_pasa_canal_a_venta(self) -> None:
        ventas_mock = MagicMock()
        motor_mock = MagicMock()
        motor_mock.calcular.return_value = MagicMock(
            vendedor=Dinero(0), cerrador=Dinero(0), agencia=Dinero(0), referido=Dinero(0)
        )
        comisiones_mock = MagicMock()
        service = _build_service(
            ventas=ventas_mock,
            motor=motor_mock,
            comisiones_repo=comisiones_mock,
        )
        cmd = _cmd(tipo_cliente=TipoCliente.DIGITAL, canal_origen="TikTok")
        service.ejecutar(cmd)
        venta_guardada = ventas_mock.guardar.call_args[0][0]
        assert venta_guardada.canal_origen == "TikTok"

    def test_notificacion_incluye_canal_para_digital(self) -> None:
        notificador_mock = MagicMock()
        motor_mock = MagicMock()
        motor_mock.calcular.return_value = MagicMock(
            vendedor=Dinero(0), cerrador=Dinero(0), agencia=Dinero(0), referido=Dinero(0)
        )
        service = _build_service(
            motor=motor_mock,
            notificador=notificador_mock,
            comisiones_repo=MagicMock(),
        )
        cmd = _cmd(tipo_cliente=TipoCliente.DIGITAL, canal_origen="Facebook")
        service.ejecutar(cmd)
        mensaje_enviado = notificador_mock.notificar.call_args[0][0]
        assert "Facebook" in mensaje_enviado

    def test_notificacion_sin_canal_para_interno(self) -> None:
        notificador_mock = MagicMock()
        motor_mock = MagicMock()
        motor_mock.calcular.return_value = MagicMock(
            vendedor=Dinero(0), cerrador=Dinero(0), agencia=Dinero(0), referido=Dinero(0)
        )
        service = _build_service(
            motor=motor_mock,
            notificador=notificador_mock,
            comisiones_repo=MagicMock(),
        )
        cmd = _cmd(tipo_cliente=TipoCliente.INTERNO, canal_origen=None)
        service.ejecutar(cmd)
        mensaje_enviado = notificador_mock.notificar.call_args[0][0]
        assert "📲 Canal:" not in mensaje_enviado
