"""Tests for Venta.cambiar_abono() — RED."""

from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.errores import (
    AbonoSuperaValorVenta,
    MismoAbono,
    VentaYaAnulada,
)
from garay.dominio.ventas.valor_objetos import Participantes


def _venta(
    valor_venta: Dinero | None = None,
    neto: Dinero | None = None,
    abono: Dinero | None = None,
) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=valor_venta or Dinero(300_000),
        neto=neto or Dinero(100_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2024, 6, 1),
        participantes=Participantes(),
        abono=abono,
    )


class TestCambiarAbono:
    def test_happy_path_establece_abono(self) -> None:
        venta = _venta(valor_venta=Dinero(300_000))
        venta.cambiar_abono(Dinero(50_000))
        assert venta.abono == Dinero(50_000)

    def test_happy_path_limpia_abono_a_none(self) -> None:
        venta = _venta(abono=Dinero(80_000))
        venta.cambiar_abono(None)
        assert venta.abono is None

    def test_abono_igual_a_valor_venta_es_valido(self) -> None:
        venta = _venta(valor_venta=Dinero(300_000))
        venta.cambiar_abono(Dinero(300_000))
        assert venta.abono == Dinero(300_000)

    def test_abono_supera_valor_venta_raises(self) -> None:
        venta = _venta(valor_venta=Dinero(300_000))
        with pytest.raises(AbonoSuperaValorVenta):
            venta.cambiar_abono(Dinero(300_001))

    def test_venta_ya_anulada_raises(self) -> None:
        venta = _venta()
        venta.anular()
        with pytest.raises(VentaYaAnulada):
            venta.cambiar_abono(Dinero(50_000))

    def test_mismo_abono_none_none_raises(self) -> None:
        venta = _venta(abono=None)
        with pytest.raises(MismoAbono):
            venta.cambiar_abono(None)

    def test_mismo_abono_valor_igual_raises(self) -> None:
        venta = _venta(abono=Dinero(50_000))
        with pytest.raises(MismoAbono):
            venta.cambiar_abono(Dinero(50_000))

    def test_cambio_de_valor_no_raises(self) -> None:
        venta = _venta(abono=Dinero(50_000))
        venta.cambiar_abono(Dinero(80_000))
        assert venta.abono == Dinero(80_000)
