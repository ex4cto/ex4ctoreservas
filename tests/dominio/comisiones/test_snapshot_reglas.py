from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.puntos_venta.entidades import PuntoDeVenta


def _reglas(**kwargs: object) -> ReglasComision:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "tipo_cliente": TipoCliente.EXTERNO,
        "porcentaje_vendedor": Decimal("20"),
        "porcentaje_cerrador": Decimal("20"),
        "porcentaje_referido_maximo": Decimal("10"),
    }
    defaults.update(kwargs)
    return ReglasComision(**defaults)  # type: ignore[arg-type]


def _punto(porcentaje_capa: Decimal = Decimal("20")) -> PuntoDeVenta:
    return PuntoDeVenta(
        id=uuid.uuid4(),
        nombre="Punto Test",
        porcentaje_capa=porcentaje_capa,
    )


class TestSnapshotReglas:
    def test_desde_reglas_sin_punto(self) -> None:
        reglas = _reglas()
        snap = SnapshotReglas.desde_reglas(reglas, None)
        assert snap.porcentaje_capa_punto == Decimal("0")
        assert snap.tipo_cliente == TipoCliente.EXTERNO
        assert snap.porcentaje_vendedor == Decimal("20")
        assert snap.porcentaje_cerrador == Decimal("20")
        assert snap.porcentaje_referido_maximo == Decimal("10")

    def test_desde_reglas_con_punto(self) -> None:
        reglas = _reglas()
        punto = _punto(Decimal("15"))
        snap = SnapshotReglas.desde_reglas(reglas, punto)
        assert snap.porcentaje_capa_punto == Decimal("15")

    def test_es_frozen(self) -> None:
        reglas = _reglas()
        snap = SnapshotReglas.desde_reglas(reglas, None)
        with pytest.raises(FrozenInstanceError):
            snap.porcentaje_vendedor = Decimal("99")  # type: ignore[misc]
