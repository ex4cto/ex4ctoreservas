"""Tests for referido lines in _construir_mensaje_privado -- Task 3.6."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.aplicacion.tiquetera.servicio import _construir_mensaje_privado
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.socios.entidades import SocioConfig
from garay.dominio.ventas.valor_objetos import Participantes

_SERVICIO_ID = uuid.uuid4()
_CLIENTE_ID = uuid.uuid4()
_FECHA = datetime.date(2026, 10, 1)
_VALOR = Dinero(500_000)
_NETO = Dinero(400_000)


def _make_cmd(referido_alias: str | None = None) -> RegistrarVentaComando:
    return RegistrarVentaComando(
        valor_venta=_VALOR,
        neto=_NETO,
        servicio_ids=[_SERVICIO_ID],
        cliente_id=_CLIENTE_ID,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_FECHA,
        participantes=Participantes(
            vendedor_nombre="Ana",
            cerrador_nombre=None,
            referido_alias=referido_alias,
        ),
        adultos=2,
        ninos=0,
        servicio_nombres=["PLAYA BLANCA"],
    )


def _make_desglose_con_referido() -> MagicMock:
    d = MagicMock()
    d.vendedor.monto = Decimal("80000")
    d.vendedor = Dinero(80_000)
    d.cerrador.monto = Decimal("0")
    d.cerrador = Dinero(0)
    d.punto_de_venta.monto = Decimal("0")
    d.punto_de_venta = Dinero(0)
    d.referido.monto = Decimal("20000")
    d.referido = Dinero(20_000)
    d.agencia = Dinero(280_000)
    d.neto_vendedor = Dinero(72_000)
    d.neto_cerrador = Dinero(0)
    # snapshot
    snap = MagicMock()
    snap.porcentaje_vendedor = Decimal("20.00")
    snap.porcentaje_cerrador = Decimal("0.00")
    snap.porcentaje_capa_punto = Decimal("0.00")
    d.snapshot = snap
    return d


def _make_desglose_sin_referido() -> MagicMock:
    d = MagicMock()
    d.vendedor.monto = Decimal("80000")
    d.vendedor = Dinero(80_000)
    d.cerrador.monto = Decimal("0")
    d.cerrador = Dinero(0)
    d.punto_de_venta.monto = Decimal("0")
    d.punto_de_venta = Dinero(0)
    d.referido.monto = Decimal("0")
    d.referido = Dinero(0)
    d.agencia = Dinero(300_000)
    d.neto_vendedor = Dinero(80_000)
    d.neto_cerrador = Dinero(0)
    snap = MagicMock()
    snap.porcentaje_vendedor = Decimal("20.00")
    snap.porcentaje_cerrador = Decimal("0.00")
    snap.porcentaje_capa_punto = Decimal("0.00")
    d.snapshot = snap
    return d


def _make_socio() -> SocioConfig:
    return SocioConfig(nombre="garay", porcentaje=Decimal("25"), telegram_id=None)


class TestConstruirMensajePrivadoReferido:
    def _call(self, desglose: object, cmd: RegistrarVentaComando) -> str:
        socio = _make_socio()
        return _construir_mensaje_privado(
            socio=socio,
            monto=Dinero(70_000),
            desglose=desglose,  # type: ignore[arg-type]
            cmd=cmd,
            split={"garay": Dinero(70_000)},
            socios=[socio],
        )

    def test_con_referido_muestra_linea_referido(self) -> None:
        desglose = _make_desglose_con_referido()
        cmd = _make_cmd(referido_alias="taxi")
        result = self._call(desglose, cmd)
        assert "taxi" in result
        assert "Referido" in result

    def test_con_referido_muestra_neto_lines_si_difieren(self) -> None:
        desglose = _make_desglose_con_referido()
        cmd = _make_cmd(referido_alias="taxi")
        result = self._call(desglose, cmd)
        assert "Neto vendedor" in result

    def test_sin_referido_no_muestra_neto_lines(self) -> None:
        desglose = _make_desglose_sin_referido()
        cmd = _make_cmd(referido_alias=None)
        result = self._call(desglose, cmd)
        assert "Referido" not in result
        assert "Neto vendedor" not in result

    def test_referido_cero_no_muestra_referido(self) -> None:
        desglose = _make_desglose_sin_referido()
        cmd = _make_cmd(referido_alias="taxi")
        result = self._call(desglose, cmd)
        # referido.monto == 0, so no referido line even if alias is set
        assert "Referido" not in result
