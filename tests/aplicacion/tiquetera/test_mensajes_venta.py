"""TDD tests for venta message builders.

M: ticket number shown in private socio DM.
N: "(sin abono)" label shown in group message when no deposit was paid.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.aplicacion.tiquetera.servicio import (
    RegistrarVentaService,
    _construir_mensaje_privado,
)
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.socios.entidades import SocioConfig
from garay.dominio.ventas.valor_objetos import Participantes

_SERVICIO_ID = uuid.uuid4()
_CLIENTE_ID = uuid.uuid4()
_FECHA = datetime.date(2026, 9, 25)
_VALOR = Dinero(200_000)
_NETO = Dinero(110_000)


def _make_cmd(
    *,
    numero_fisico: str | None = None,
    abono: Dinero | None = None,
) -> RegistrarVentaComando:
    return RegistrarVentaComando(
        valor_venta=_VALOR,
        neto=_NETO,
        servicio_ids=[_SERVICIO_ID],
        cliente_id=_CLIENTE_ID,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_FECHA,
        participantes=Participantes(),
        adultos=2,
        ninos=0,
        servicio_nombres=["PLAYA BLANCA"],
        numero_fisico=numero_fisico,
        abono=abono,
    )


def _make_desglose() -> MagicMock:
    d = MagicMock()
    d.vendedor.monto = Decimal("0")
    d.cerrador.monto = Decimal("0")
    d.punto_de_venta.monto = Decimal("0")
    d.agencia = Dinero(45_000)
    return d


def _make_socio() -> SocioConfig:
    return SocioConfig(nombre="garay", porcentaje=Decimal("25"), telegram_id=None)


def _build_service() -> tuple[RegistrarVentaService, MagicMock]:
    notificador = MagicMock()
    notificador.notificar.return_value = None
    motor = MagicMock()
    motor.calcular.return_value = _make_desglose()
    svc = RegistrarVentaService(
        ventas=MagicMock(),
        reglas_repo=MagicMock(),
        tiqueteras=MagicMock(),
        puntos_repo=MagicMock(),
        motor=motor,
        notificador=notificador,
        grupo_id="grupo-test",
        comisiones_repo=MagicMock(),
        socios_config=MagicMock(listar=MagicMock(return_value=[])),
    )
    return svc, notificador


# ---------------------------------------------------------------------------
# M — Ticket number in private socio DM
# ---------------------------------------------------------------------------


class TestDmPrivadoTicket:
    def _call(self, numero_fisico: str | None) -> str:
        socio = _make_socio()
        return _construir_mensaje_privado(
            socio=socio,
            monto=Dinero(11_250),
            desglose=_make_desglose(),
            cmd=_make_cmd(numero_fisico=numero_fisico),
            split={"garay": Dinero(11_250)},
            socios=[socio],
        )

    def test_ticket_presente_aparece_en_dm(self) -> None:
        result = self._call("T-001")
        assert "T-001" in result

    def test_sin_ticket_no_aparece_linea_ticket(self) -> None:
        result = self._call(None)
        assert "Ticket" not in result


# ---------------------------------------------------------------------------
# N — "(sin abono)" label in group message
# ---------------------------------------------------------------------------


class TestGrupoSinAbono:
    def _grupo_msg(self, abono: Dinero | None) -> str:
        svc, notificador = _build_service()
        svc.ejecutar(_make_cmd(abono=abono))
        return str(notificador.notificar.call_args[0][0])

    def test_sin_abono_muestra_label(self) -> None:
        msg = self._grupo_msg(abono=None)
        assert "(sin abono)" in msg

    def test_con_abono_no_muestra_label(self) -> None:
        msg = self._grupo_msg(abono=Dinero(50_000))
        assert "(sin abono)" not in msg
        assert "Abono" in msg
