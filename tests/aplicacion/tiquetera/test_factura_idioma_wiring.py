"""TDD RED — factura_idioma wired through command and RegistrarVentaService."""

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


class TestRegistrarVentaComandoFacturaIdioma:
    def test_comando_acepta_factura_idioma(self) -> None:
        assert _cmd(factura_idioma="en").factura_idioma == "en"

    def test_comando_factura_idioma_default_es(self) -> None:
        assert _cmd().factura_idioma == "es"


class TestRegistrarVentaServiceFacturaIdioma:
    def test_servicio_pasa_idioma_a_venta(self) -> None:
        ventas_mock = MagicMock()
        motor_mock = MagicMock()
        motor_mock.calcular.return_value = MagicMock(
            vendedor=Dinero(0), cerrador=Dinero(0), agencia=Dinero(0), referido=Dinero(0)
        )
        service = _build_service(
            ventas=ventas_mock,
            motor=motor_mock,
            comisiones_repo=MagicMock(),
        )
        cmd = _cmd(tipo_cliente=TipoCliente.DIGITAL, factura_idioma="en")

        service.ejecutar(cmd)

        venta_guardada = ventas_mock.guardar.call_args[0][0]
        assert venta_guardada.factura_idioma == "en"
