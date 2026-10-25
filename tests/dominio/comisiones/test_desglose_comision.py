from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente


def _snapshot() -> SnapshotReglas:
    reglas = ReglasComision(
        id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("20"),
        porcentaje_cerrador=Decimal("20"),
    )
    return SnapshotReglas.desde_reglas(reglas, None)

def _desglose(**kwargs: object) -> DesgloseComision:
    defaults: dict[str, object] = {
        "vendedor": Dinero(10_000),
        "cerrador": Dinero(5_000),
        "punto_de_venta": Dinero(3_000),
        "referido": Dinero(2_000),
        "agencia": Dinero(1_000),
        "snapshot": _snapshot(),
        "neto_vendedor": Dinero(9_000),
        "neto_cerrador": Dinero(4_500),
    }
    defaults.update(kwargs)
    return DesgloseComision(**defaults)  # type: ignore[arg-type]

class TestDesgloseComision:
    def test_creacion_valida(self) -> None:
        d = _desglose()
        assert d.vendedor == Dinero(10_000)
        assert d.cerrador == Dinero(5_000)
        assert d.punto_de_venta == Dinero(3_000)
        assert d.referido == Dinero(2_000)
        assert d.agencia == Dinero(1_000)

    def test_neto_vendedor_presente(self) -> None:
        """Task 1.4: neto_vendedor must be a required field on DesgloseComision."""
        d = _desglose(neto_vendedor=Dinero(9_000))
        assert d.neto_vendedor == Dinero(9_000)

    def test_neto_cerrador_presente(self) -> None:
        """Task 1.4: neto_cerrador must be a required field on DesgloseComision."""
        d = _desglose(neto_cerrador=Dinero(4_500))
        assert d.neto_cerrador == Dinero(4_500)

    def test_sin_neto_vendedor_falla(self) -> None:
        """Task 1.4: constructing DesgloseComision without neto_vendedor must fail."""
        with pytest.raises(TypeError):
            DesgloseComision(  # type: ignore[call-arg]
                vendedor=Dinero(10_000),
                cerrador=Dinero(5_000),
                punto_de_venta=Dinero(3_000),
                referido=Dinero(2_000),
                agencia=Dinero(1_000),
                snapshot=_snapshot(),
                # neto_vendedor intentionally missing
                neto_cerrador=Dinero(4_500),
            )

    def test_sin_neto_cerrador_falla(self) -> None:
        """Task 1.4: constructing DesgloseComision without neto_cerrador must fail."""
        with pytest.raises(TypeError):
            DesgloseComision(  # type: ignore[call-arg]
                vendedor=Dinero(10_000),
                cerrador=Dinero(5_000),
                punto_de_venta=Dinero(3_000),
                referido=Dinero(2_000),
                agencia=Dinero(1_000),
                snapshot=_snapshot(),
                neto_vendedor=Dinero(9_000),
                # neto_cerrador intentionally missing
            )

    def test_es_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        d = _desglose()
        with pytest.raises(FrozenInstanceError):
            d.vendedor = Dinero(0)  # type: ignore[misc]

    def test_igualdad_por_valor(self) -> None:
        a = _desglose()
        b = _desglose()
        assert a == b
