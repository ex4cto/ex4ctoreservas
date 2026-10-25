"""Tests for task 1.9: PagoReferido domain entity."""

from __future__ import annotations

import datetime
import uuid

from garay.dominio.comun.dinero import Dinero
from garay.dominio.liquidaciones.entidades import PagoReferido


class TestPagoReferido:
    def test_construction_with_required_fields(self) -> None:
        """Task 1.9: PagoReferido accepts all required fields."""
        pago = PagoReferido(
            id=uuid.uuid4(),
            venta_id=uuid.uuid4(),
            referido_alias="taxi",
            monto=Dinero(15_000),
            fecha_pago=datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.UTC),
            registrado_por_telegram_id=5870211102,
            registrado_por_nombre="Ryan",
        )
        assert pago.referido_alias == "taxi"
        assert pago.monto == Dinero(15_000)

    def test_registrado_por_nombre_can_be_none(self) -> None:
        pago = PagoReferido(
            id=uuid.uuid4(),
            venta_id=uuid.uuid4(),
            referido_alias="moto",
            monto=Dinero(10_000),
            fecha_pago=datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.UTC),
            registrado_por_telegram_id=5870211102,
            registrado_por_nombre=None,
        )
        assert pago.registrado_por_nombre is None

    def test_pago_referido_is_frozen(self) -> None:
        """Task 1.9: PagoReferido must be frozen (immutable)."""
        import pytest

        pago = PagoReferido(
            id=uuid.uuid4(),
            venta_id=uuid.uuid4(),
            referido_alias="taxi",
            monto=Dinero(15_000),
            fecha_pago=datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.UTC),
            registrado_por_telegram_id=5870211102,
            registrado_por_nombre="Ryan",
        )
        with pytest.raises((AttributeError, TypeError)):
            pago.referido_alias = "otro"  # type: ignore[misc]
