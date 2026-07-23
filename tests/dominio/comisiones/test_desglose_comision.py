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
        porcentaje_referido_maximo=Decimal("10"),
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

    def test_es_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        d = _desglose()
        with pytest.raises(FrozenInstanceError):
            d.vendedor = Dinero(0)  # type: ignore[misc]

    def test_igualdad_por_valor(self) -> None:
        a = _desglose()
        b = _desglose()
        assert a == b
