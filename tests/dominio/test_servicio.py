"""Tests for the Servicio domain entity — precio_sugerido fields."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from garay.dominio.servicios.entidades import Servicio


def _servicio(**kwargs: object) -> Servicio:
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(),
        numero=1,
        nombre="Tour Test",
    )
    defaults.update(kwargs)
    return Servicio(**defaults)  # type: ignore[arg-type]


class TestPrecioSugeridoAdulto:
    def test_valor_positivo_aceptado(self) -> None:
        """A positive Decimal for precio_sugerido_adulto must not raise."""
        s = _servicio(precio_sugerido_adulto=Decimal("100000"))
        assert s.precio_sugerido_adulto == Decimal("100000")

    def test_none_aceptado(self) -> None:
        """None is a valid value for precio_sugerido_adulto."""
        s = _servicio(precio_sugerido_adulto=None)
        assert s.precio_sugerido_adulto is None

    def test_cero_rechazado(self) -> None:
        """Zero raises ValueError."""
        with pytest.raises(ValueError):
            _servicio(precio_sugerido_adulto=Decimal("0"))

    def test_negativo_rechazado(self) -> None:
        """A negative Decimal raises ValueError."""
        with pytest.raises(ValueError):
            _servicio(precio_sugerido_adulto=Decimal("-1"))

    def test_valor_default_es_none(self) -> None:
        """precio_sugerido_adulto defaults to None when not provided."""
        s = _servicio()
        assert s.precio_sugerido_adulto is None


class TestPrecioSugeridoNino:
    def test_valor_positivo_aceptado(self) -> None:
        """A positive Decimal for precio_sugerido_nino must not raise."""
        s = _servicio(precio_sugerido_nino=Decimal("80000"))
        assert s.precio_sugerido_nino == Decimal("80000")

    def test_none_aceptado(self) -> None:
        """None is a valid value for precio_sugerido_nino."""
        s = _servicio(precio_sugerido_nino=None)
        assert s.precio_sugerido_nino is None

    def test_cero_rechazado(self) -> None:
        """Zero raises ValueError."""
        with pytest.raises(ValueError):
            _servicio(precio_sugerido_nino=Decimal("0"))

    def test_negativo_rechazado(self) -> None:
        """A negative Decimal raises ValueError."""
        with pytest.raises(ValueError):
            _servicio(precio_sugerido_nino=Decimal("-500"))

    def test_valor_default_es_none(self) -> None:
        """precio_sugerido_nino defaults to None when not provided."""
        s = _servicio()
        assert s.precio_sugerido_nino is None


class TestAmbosFieldsIndependientes:
    def test_ambos_positivos(self) -> None:
        """Both fields can be set simultaneously."""
        s = _servicio(
            precio_sugerido_adulto=Decimal("150000"),
            precio_sugerido_nino=Decimal("90000"),
        )
        assert s.precio_sugerido_adulto == Decimal("150000")
        assert s.precio_sugerido_nino == Decimal("90000")

    def test_adulto_valido_nino_invalido_rechaza(self) -> None:
        """Valid adulto + invalid nino still raises."""
        with pytest.raises(ValueError):
            _servicio(
                precio_sugerido_adulto=Decimal("150000"),
                precio_sugerido_nino=Decimal("0"),
            )
