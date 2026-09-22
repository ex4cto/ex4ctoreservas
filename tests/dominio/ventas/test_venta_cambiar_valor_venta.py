"""Tests for Venta.cambiar_valor_venta() — Phase 2.3.2 RED."""

from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.comun.dinero import MontoInvalido
from garay.dominio.ventas.errores import (
    MismoValorVenta,
    NetoIgualOSuperaValorVenta,
    ValorVentaMenorQueAbono,
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


class TestCambiarValorVenta:
    """Venta.cambiar_valor_venta() must enforce edit-time rules."""

    def test_happy_path_actualiza_valor_venta(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100), abono=Dinero(150))
        venta.cambiar_valor_venta(Dinero(400))
        assert venta.valor_venta == Dinero(400)

    def test_happy_path_ganancia_recomputada(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100), abono=Dinero(150))
        venta.cambiar_valor_venta(Dinero(400))
        assert venta.ganancia == Dinero(300)

    def test_block_valor_menor_que_abono(self) -> None:
        # neto=50, valor_venta=300, abono=200 → try new valor_venta=180 (< abono=200)
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(50), abono=Dinero(200))
        with pytest.raises(ValorVentaMenorQueAbono):
            venta.cambiar_valor_venta(Dinero(180))

    def test_boundary_valor_igual_abono_allowed(self) -> None:
        """valor_venta == abono is ALLOWED (only strict less-than is blocked)."""
        # neto=50, abono=150 → new valor_venta=150 (== abono, allowed; neto=50 < 150)
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(50), abono=Dinero(150))
        venta.cambiar_valor_venta(Dinero(150))
        assert venta.valor_venta == Dinero(150)

    def test_block_neto_supera_nuevo_valor_venta(self) -> None:
        """After change, neto must still be < valor_venta."""
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        with pytest.raises(NetoIgualOSuperaValorVenta):
            venta.cambiar_valor_venta(Dinero(100))  # neto == new valor_venta → blocked

    def test_block_idempotente_mismo_valor_venta(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        with pytest.raises(MismoValorVenta):
            venta.cambiar_valor_venta(Dinero(300))

    def test_block_venta_ya_anulada(self) -> None:
        venta = _venta()
        venta.anular()
        with pytest.raises(VentaYaAnulada):
            venta.cambiar_valor_venta(Dinero(400))

    def test_entity_unchanged_on_block(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(50), abono=Dinero(200))
        try:
            venta.cambiar_valor_venta(Dinero(180))
        except ValorVentaMenorQueAbono:
            pass
        assert venta.valor_venta == Dinero(300)

    def test_float_rejected(self) -> None:
        with pytest.raises(MontoInvalido):
            Dinero(400.0)  # type: ignore[arg-type]

    def test_no_abono_no_abono_check(self) -> None:
        """When abono is None, no abono check runs."""
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100), abono=None)
        venta.cambiar_valor_venta(Dinero(150))
        assert venta.valor_venta == Dinero(150)
