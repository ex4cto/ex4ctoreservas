"""Tests for Venta.cambiar_neto() — Phase 2.3.1 RED."""

from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.comun.dinero import MontoInvalido
from garay.dominio.ventas.errores import (
    MismoNeto,
    NetoIgualOSuperaValorVenta,
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
        valor_venta=valor_venta or Dinero(300),
        neto=neto or Dinero(100),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2024, 6, 1),
        participantes=Participantes(),
        abono=abono,
    )


class TestCambiarNeto:
    """Venta.cambiar_neto() must enforce edit-time rules."""

    def test_happy_path_actualiza_neto(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        venta.cambiar_neto(Dinero(80))
        assert venta.neto == Dinero(80)

    def test_happy_path_ganancia_recomputada(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        venta.cambiar_neto(Dinero(80))
        assert venta.ganancia == Dinero(220)

    def test_block_neto_igual_valor_venta(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        with pytest.raises(NetoIgualOSuperaValorVenta):
            venta.cambiar_neto(Dinero(300))

    def test_block_neto_mayor_que_valor_venta(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        with pytest.raises(NetoIgualOSuperaValorVenta):
            venta.cambiar_neto(Dinero(400))

    def test_block_idempotente_mismo_neto(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        with pytest.raises(MismoNeto):
            venta.cambiar_neto(Dinero(100))

    def test_block_venta_ya_anulada(self) -> None:
        venta = _venta()
        venta.anular()
        with pytest.raises(VentaYaAnulada):
            venta.cambiar_neto(Dinero(80))

    def test_entity_unchanged_on_block(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        try:
            venta.cambiar_neto(Dinero(300))
        except NetoIgualOSuperaValorVenta:
            pass
        assert venta.neto == Dinero(100)

    def test_float_rejected(self) -> None:
        """Dinero rejects float at construction — no float can reach cambiar_neto."""
        with pytest.raises(MontoInvalido):
            Dinero(80.0)  # type: ignore[arg-type]

    def test_neto_one_less_than_valor_venta_allowed(self) -> None:
        """neto = valor_venta - 1 must be allowed (strict < threshold)."""
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        venta.cambiar_neto(Dinero(299))
        assert venta.neto == Dinero(299)
