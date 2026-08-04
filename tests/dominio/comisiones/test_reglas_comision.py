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


class TestReglasComisionCamposNuevos:
    """WU-1: punto_de_venta_nombre and numero_personas fields (REQ-06 / JD-6)."""

    def test_acepta_punto_de_venta_nombre_none_por_defecto(self) -> None:
        r = _reglas()
        assert r.punto_de_venta_nombre is None

    def test_acepta_punto_de_venta_nombre_no_none(self) -> None:
        r = _reglas(punto_de_venta_nombre="Crespo")
        assert r.punto_de_venta_nombre == "Crespo"

    def test_acepta_numero_personas_none_por_defecto(self) -> None:
        r = _reglas()
        assert r.numero_personas is None

    def test_acepta_numero_personas_1(self) -> None:
        r = _reglas(numero_personas=1)
        assert r.numero_personas == 1

    def test_acepta_numero_personas_2(self) -> None:
        r = _reglas(numero_personas=2)
        assert r.numero_personas == 2

    def test_numero_personas_0_invalido(self) -> None:
        with pytest.raises(ValueError):
            _reglas(numero_personas=0)

    def test_numero_personas_3_invalido(self) -> None:
        with pytest.raises(ValueError):
            _reglas(numero_personas=3)

    def test_numero_personas_negativo_invalido(self) -> None:
        with pytest.raises(ValueError):
            _reglas(numero_personas=-1)

    def test_campos_nuevos_son_ultimos_no_rompe_posicionales(self) -> None:
        # Non-defaulted fields must all come before defaulted fields.
        # This constructs with keyword args matching all non-defaulted fields positionally.
        r = ReglasComision(
            id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
            porcentaje_vendedor=Decimal("30"),
            porcentaje_cerrador=Decimal("30"),
            porcentaje_referido_maximo=Decimal("10"),
            punto_de_venta_nombre="Crespo",
            numero_personas=1,
        )
        assert r.punto_de_venta_nombre == "Crespo"
        assert r.numero_personas == 1
