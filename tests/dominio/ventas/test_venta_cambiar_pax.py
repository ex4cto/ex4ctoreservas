"""Tests for Venta.cambiar_pax() — RED first, then GREEN."""

from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.errores import CantidadInvalida, VentaYaAnulada
from garay.dominio.ventas.valor_objetos import Participantes


def _venta(adultos: int = 2, ninos: int = 1) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(500_000),
        neto=Dinero(300_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2025, 1, 15),
        participantes=Participantes(),
        adultos=adultos,
        ninos=ninos,
    )

class TestCambiarPax:
    def test_happy_path_actualiza_adultos_y_ninos(self) -> None:
        v = _venta(adultos=2, ninos=1)
        v.cambiar_pax(3, 2)
        assert v.adultos == 3
        assert v.ninos == 2

    def test_happy_path_solo_adultos_sin_ninos(self) -> None:
        v = _venta(adultos=1, ninos=0)
        v.cambiar_pax(4, 0)
        assert v.adultos == 4
        assert v.ninos == 0

    def test_block_adultos_cero(self) -> None:
        v = _venta()
        with pytest.raises(CantidadInvalida):
            v.cambiar_pax(0, 1)

    def test_block_adultos_negativo(self) -> None:
        v = _venta()
        with pytest.raises(CantidadInvalida):
            v.cambiar_pax(-1, 0)

    def test_block_ninos_negativo(self) -> None:
        v = _venta()
        with pytest.raises(CantidadInvalida):
            v.cambiar_pax(1, -1)

    def test_block_venta_anulada(self) -> None:
        v = _venta()
        v.anular()
        with pytest.raises(VentaYaAnulada):
            v.cambiar_pax(2, 0)

    def test_mismos_valores_igual_se_permite(self) -> None:
        """cambiar_pax does not have an idempotency guard — same values are accepted."""
        v = _venta(adultos=2, ninos=1)
        v.cambiar_pax(2, 1)  # must not raise
        assert v.adultos == 2
        assert v.ninos == 1
