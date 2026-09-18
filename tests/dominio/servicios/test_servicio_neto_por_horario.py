"""Tests for Servicio.netos_por_horario field and neto_para_horario() method.

TDD: RED phase — these tests are written before the implementation.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from garay.dominio.servicios.entidades import Servicio


def _servicio(**kwargs: object) -> Servicio:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "numero": 1,
        "nombre": "City Tour",
    }
    defaults.update(kwargs)
    return Servicio(**defaults)  # type: ignore[arg-type]


class TestNetosHorarioField:
    """Servicio.netos_por_horario field defaults and construction."""

    def test_default_es_dict_vacio(self) -> None:
        """Servicio constructed without netos_por_horario defaults to {}."""
        s = _servicio()
        assert s.netos_por_horario == {}

    def test_acepta_dict_con_decimales(self) -> None:
        """Servicio accepts netos_por_horario with Decimal values."""
        netos = {"08:00": Decimal("60000"), "13:00": Decimal("55000")}
        s = _servicio(netos_por_horario=netos)
        assert s.netos_por_horario == netos

    def test_rechaza_float_en_valores(self) -> None:
        """Servicio raises TypeError when a float value is passed in netos_por_horario."""
        with pytest.raises(TypeError):
            _servicio(netos_por_horario={"08:00": 60000.0})

    def test_no_afecta_otros_campos(self) -> None:
        """Adding netos_por_horario does not change other Servicio fields."""
        s = _servicio(
            precio_neto_adulto=Decimal("50000"),
            netos_por_horario={"08:00": Decimal("60000")},
        )
        assert s.precio_neto_adulto == Decimal("50000")
        assert s.nombre == "City Tour"


class TestNetoPorHorario:
    """Servicio.neto_para_horario() resolution logic."""

    def test_horario_existente_devuelve_neto_especifico(self) -> None:
        """neto_para_horario("08:00") returns the per-horario Decimal when key exists."""
        s = _servicio(
            netos_por_horario={
                "08:00": Decimal("60000"),
                "13:00": Decimal("55000"),
            },
            precio_neto_adulto=Decimal("50000"),
        )
        assert s.neto_para_horario("08:00") == Decimal("60000")

    def test_horario_tarde_devuelve_neto_especifico(self) -> None:
        """neto_para_horario("13:00") returns the per-horario Decimal for the afternoon slot."""
        s = _servicio(
            netos_por_horario={
                "08:00": Decimal("60000"),
                "13:00": Decimal("55000"),
            },
            precio_neto_adulto=Decimal("50000"),
        )
        assert s.neto_para_horario("13:00") == Decimal("55000")

    def test_horario_no_configurado_cae_a_precio_neto_adulto(self) -> None:
        """neto_para_horario("09:00") falls back to precio_neto_adulto when key missing."""
        s = _servicio(
            netos_por_horario={"08:00": Decimal("60000")},
            precio_neto_adulto=Decimal("50000"),
        )
        assert s.neto_para_horario("09:00") == Decimal("50000")

    def test_horario_none_cae_a_precio_neto_adulto(self) -> None:
        """neto_para_horario(None) falls back to precio_neto_adulto."""
        s = _servicio(
            netos_por_horario={"08:00": Decimal("60000")},
            precio_neto_adulto=Decimal("50000"),
        )
        assert s.neto_para_horario(None) == Decimal("50000")

    def test_netos_vacio_cae_a_precio_neto_adulto(self) -> None:
        """neto_para_horario("08:00") returns precio_neto_adulto when netos_por_horario is {}."""
        s = _servicio(
            netos_por_horario={},
            precio_neto_adulto=Decimal("50000"),
        )
        assert s.neto_para_horario("08:00") == Decimal("50000")

    def test_sin_precio_neto_adulto_devuelve_none(self) -> None:
        """When netos_por_horario empty and precio_neto_adulto is None, returns None."""
        s = _servicio(netos_por_horario={}, precio_neto_adulto=None)
        assert s.neto_para_horario("08:00") is None

    def test_horario_none_sin_precio_neto_devuelve_none(self) -> None:
        """When horario is None and precio_neto_adulto is None, returns None."""
        s = _servicio(
            netos_por_horario={"08:00": Decimal("60000")},
            precio_neto_adulto=None,
        )
        assert s.neto_para_horario(None) is None
