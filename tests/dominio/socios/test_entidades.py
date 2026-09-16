"""Tests for socios domain entities — RED phase."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.socios.entidades import PagoSocio, SocioConfig


class TestSocioConfig:
    def test_creacion_valida_con_telegram_id(self) -> None:
        config = SocioConfig(
            nombre="garay",
            porcentaje=Decimal("50"),
            telegram_id=123456789,
        )
        assert config.nombre == "garay"
        assert config.porcentaje == Decimal("50")
        assert config.telegram_id == 123456789

    def test_creacion_valida_sin_telegram_id(self) -> None:
        config = SocioConfig(
            nombre="empresa",
            porcentaje=Decimal("50"),
            telegram_id=None,
        )
        assert config.telegram_id is None

    def test_acepta_porcentaje_fraccionario(self) -> None:
        config = SocioConfig(
            nombre="ryan",
            porcentaje=Decimal("25.50"),
            telegram_id=None,
        )
        assert config.porcentaje == Decimal("25.50")

    def test_es_dataclass(self) -> None:
        import dataclasses

        assert dataclasses.is_dataclass(SocioConfig)

    def test_es_frozen(self) -> None:
        config = SocioConfig(
            nombre="garay",
            porcentaje=Decimal("50"),
            telegram_id=None,
        )
        with pytest.raises(FrozenInstanceError):
            config.nombre = "otro"  # type: ignore[misc]


class TestPagoSocio:
    def _pago(self, tipo: str = "total") -> PagoSocio:
        return PagoSocio(
            id=uuid.uuid4(),
            nombre_socio="garay",
            monto=Dinero("500000"),
            fecha=datetime.date(2026, 9, 15),
            tipo=tipo,
            nota=None,
            registrado_en=datetime.datetime(2026, 9, 15, 10, 0, 0),
        )

    def test_creacion_tipo_total(self) -> None:
        pago = self._pago("total")
        assert pago.tipo == "total"
        assert pago.nombre_socio == "garay"
        assert pago.monto == Dinero("500000")

    def test_creacion_tipo_parcial(self) -> None:
        pago = self._pago("parcial")
        assert pago.tipo == "parcial"

    def test_acepta_nota_none(self) -> None:
        pago = self._pago()
        assert pago.nota is None

    def test_acepta_nota_texto(self) -> None:
        pago = PagoSocio(
            id=uuid.uuid4(),
            nombre_socio="ryan",
            monto=Dinero("200000"),
            fecha=datetime.date(2026, 9, 15),
            tipo="parcial",
            nota="Pago adelanto",
            registrado_en=datetime.datetime(2026, 9, 15, 10, 0, 0),
        )
        assert pago.nota == "Pago adelanto"

    def test_es_dataclass(self) -> None:
        import dataclasses

        assert dataclasses.is_dataclass(PagoSocio)

    def test_igualdad_por_identidad_id(self) -> None:
        id_ = uuid.uuid4()
        a = PagoSocio(
            id=id_,
            nombre_socio="garay",
            monto=Dinero("100000"),
            fecha=datetime.date(2026, 9, 15),
            tipo="total",
            nota=None,
            registrado_en=datetime.datetime(2026, 9, 15, 10, 0, 0),
        )
        b = PagoSocio(
            id=id_,
            nombre_socio="garay",
            monto=Dinero("100000"),
            fecha=datetime.date(2026, 9, 15),
            tipo="total",
            nota=None,
            registrado_en=datetime.datetime(2026, 9, 15, 10, 0, 0),
        )
        assert a == b
