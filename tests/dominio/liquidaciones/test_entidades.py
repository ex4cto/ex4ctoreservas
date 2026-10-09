"""Tests for PagoFreelancer domain entity."""

from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.liquidaciones.entidades import PagoFreelancer


class TestPagoFreelancer:
    def test_can_be_constructed_with_all_required_fields(self) -> None:
        """PagoFreelancer accepts all required fields."""
        pago = PagoFreelancer(
            id=uuid.uuid4(),
            freelancer_id=uuid.uuid4(),
            monto=Dinero(100_000),
            desde=datetime.date(2026, 10, 1),
            hasta=datetime.date(2026, 10, 7),
            fecha_pago=datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.timezone.utc),
            registrado_por_telegram_id=5870211102,
            registrado_por_nombre="Ryan",
        )

        assert pago.monto == Dinero(100_000)
        assert pago.desde == datetime.date(2026, 10, 1)
        assert pago.hasta == datetime.date(2026, 10, 7)
        assert pago.registrado_por_telegram_id == 5870211102
        assert pago.registrado_por_nombre == "Ryan"

    def test_registrado_por_nombre_can_be_none(self) -> None:
        """registrado_por_nombre is optional (can be None)."""
        pago = PagoFreelancer(
            id=uuid.uuid4(),
            freelancer_id=uuid.uuid4(),
            monto=Dinero(50_000),
            desde=datetime.date(2026, 10, 1),
            hasta=datetime.date(2026, 10, 7),
            fecha_pago=datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.timezone.utc),
            registrado_por_telegram_id=5870211102,
            registrado_por_nombre=None,
        )

        assert pago.registrado_por_nombre is None

    def test_is_a_dataclass(self) -> None:
        """PagoFreelancer is a dataclass (id can be assigned post-construction)."""
        import dataclasses

        assert dataclasses.is_dataclass(PagoFreelancer)

    def test_id_can_be_reassigned(self) -> None:
        """PagoFreelancer is not frozen — id and other fields can be updated."""
        pago = PagoFreelancer(
            id=uuid.uuid4(),
            freelancer_id=uuid.uuid4(),
            monto=Dinero(100_000),
            desde=datetime.date(2026, 10, 1),
            hasta=datetime.date(2026, 10, 7),
            fecha_pago=datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.timezone.utc),
            registrado_por_telegram_id=5870211102,
            registrado_por_nombre=None,
        )
        new_id = uuid.uuid4()
        pago.id = new_id
        assert pago.id == new_id
