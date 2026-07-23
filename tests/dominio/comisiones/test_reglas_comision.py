from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from garay.dominio.comisiones.errores import PorcentajeInvalidoRegla
from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.tipos import TipoCliente


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


class TestReglasComision:
    def test_creacion_valida(self) -> None:
        r = _reglas()
        assert r.porcentaje_vendedor == Decimal("20")
        assert r.porcentaje_cerrador == Decimal("20")
        assert r.porcentaje_referido_maximo == Decimal("10")

    def test_porcentajes_negativos_invalidos(self) -> None:
        with pytest.raises(PorcentajeInvalidoRegla):
            _reglas(porcentaje_vendedor=Decimal("-1"))

        with pytest.raises(PorcentajeInvalidoRegla):
            _reglas(porcentaje_cerrador=Decimal("-5"))

    def test_suma_mayor_cien_invalida(self) -> None:
        with pytest.raises(PorcentajeInvalidoRegla):
            _reglas(porcentaje_vendedor=Decimal("60"), porcentaje_cerrador=Decimal("60"))

    def test_referido_mayor_10_invalido(self) -> None:
        with pytest.raises(PorcentajeInvalidoRegla):
            _reglas(porcentaje_referido_maximo=Decimal("11"))

    def test_referido_exactamente_10_valido(self) -> None:
        r = _reglas(porcentaje_referido_maximo=Decimal("10"))
        assert r.porcentaje_referido_maximo == Decimal("10")

    def test_agencia_recibe_residual(self) -> None:
        # vendedor=20 + cerrador=20 + punto=0 → agencia absorbs 60%
        # This is verified at motor level; here we confirm valid config is accepted.
        r = _reglas(porcentaje_vendedor=Decimal("20"), porcentaje_cerrador=Decimal("20"))
        residual = Decimal("100") - r.porcentaje_vendedor - r.porcentaje_cerrador
        assert residual == Decimal("60")

    def test_identidad_por_id(self) -> None:
        id1 = uuid.uuid4()
        id2 = uuid.uuid4()
        a = _reglas(id=id1)
        b = _reglas(id=id1)
        c = _reglas(id=id2)
        assert a == b
        assert a != c
        assert hash(a) == hash(b)
        assert hash(a) != hash(c)
