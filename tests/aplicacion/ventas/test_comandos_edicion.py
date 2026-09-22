"""Tests for EditarNetoVentaComando and EditarValorVentaComando — Phase 2.4 RED."""

from __future__ import annotations

import dataclasses
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero


class TestEditarNetoVentaComando:
    def test_importable(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarNetoVentaComando

        assert EditarNetoVentaComando is not None

    def test_frozen_dataclass_fields(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarNetoVentaComando

        fields = {f.name for f in dataclasses.fields(EditarNetoVentaComando)}
        assert fields == {
            "venta_id",
            "nuevo_neto",
            "motivo",
            "realizada_por_telegram_id",
            "realizada_por_nombre",
        }

    def test_immutable(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarNetoVentaComando

        cmd = EditarNetoVentaComando(
            venta_id=uuid.uuid4(),
            nuevo_neto=Dinero(80),
            motivo="test",
            realizada_por_telegram_id=1,
            realizada_por_nombre="Admin",
        )
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            cmd.motivo = "changed"  # type: ignore[misc]

    def test_campo_tipos(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarNetoVentaComando

        vid = uuid.uuid4()
        cmd = EditarNetoVentaComando(
            venta_id=vid,
            nuevo_neto=Dinero(80),
            motivo="reduccion de neto",
            realizada_por_telegram_id=42,
            realizada_por_nombre="Admin",
        )
        assert cmd.venta_id == vid
        assert cmd.nuevo_neto == Dinero(80)
        assert cmd.motivo == "reduccion de neto"
        assert cmd.realizada_por_telegram_id == 42
        assert cmd.realizada_por_nombre == "Admin"

    def test_nombre_opcional_none(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarNetoVentaComando

        cmd = EditarNetoVentaComando(
            venta_id=uuid.uuid4(),
            nuevo_neto=Dinero(80),
            motivo="test",
            realizada_por_telegram_id=1,
            realizada_por_nombre=None,
        )
        assert cmd.realizada_por_nombre is None


class TestEditarValorVentaComando:
    def test_importable(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarValorVentaComando

        assert EditarValorVentaComando is not None

    def test_frozen_dataclass_fields(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarValorVentaComando

        fields = {f.name for f in dataclasses.fields(EditarValorVentaComando)}
        assert fields == {
            "venta_id",
            "nuevo_valor_venta",
            "motivo",
            "realizada_por_telegram_id",
            "realizada_por_nombre",
        }

    def test_immutable(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarValorVentaComando

        cmd = EditarValorVentaComando(
            venta_id=uuid.uuid4(),
            nuevo_valor_venta=Dinero(400),
            motivo="test",
            realizada_por_telegram_id=1,
            realizada_por_nombre="Admin",
        )
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            cmd.motivo = "changed"  # type: ignore[misc]

    def test_campo_tipos(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarValorVentaComando

        vid = uuid.uuid4()
        cmd = EditarValorVentaComando(
            venta_id=vid,
            nuevo_valor_venta=Dinero(400),
            motivo="ajuste precio",
            realizada_por_telegram_id=42,
            realizada_por_nombre=None,
        )
        assert cmd.venta_id == vid
        assert cmd.nuevo_valor_venta == Dinero(400)
        assert cmd.motivo == "ajuste precio"
        assert cmd.realizada_por_nombre is None
