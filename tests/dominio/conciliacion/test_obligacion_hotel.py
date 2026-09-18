"""Tests for ObligacionHotel domain entity."""

from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.comun.dinero import Dinero


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _obligacion(**kwargs: object) -> object:
    from garay.dominio.conciliacion.entidades import ObligacionHotel

    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "punto_de_venta_nombre": "Hotel Marie",
        "receptor_nombre": "Abel",
        "monto_cuota_dia_1": Dinero(1_000_000),
        "monto_cuota_dia_2": Dinero(1_000_000),
        "dia_pago_1": 15,
        "dia_pago_2": 30,
        "deuda_inicial": Dinero(0),
        "fecha_deuda_inicial": datetime.date(2026, 1, 1),
        "activa": True,
    }
    defaults.update(kwargs)
    return ObligacionHotel(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests — entity fields
# ---------------------------------------------------------------------------


class TestObligacionHotelCampos:
    def test_creacion_valida(self) -> None:
        from garay.dominio.conciliacion.entidades import ObligacionHotel

        oid = uuid.uuid4()
        o = ObligacionHotel(
            id=oid,
            punto_de_venta_nombre="Hotel Marie",
            receptor_nombre="Abel",
            monto_cuota_dia_1=Dinero(1_000_000),
            monto_cuota_dia_2=Dinero(1_000_000),
            dia_pago_1=15,
            dia_pago_2=30,
            deuda_inicial=Dinero(0),
            fecha_deuda_inicial=datetime.date(2026, 1, 1),
            activa=True,
        )
        assert o.id == oid
        assert o.punto_de_venta_nombre == "Hotel Marie"
        assert o.receptor_nombre == "Abel"
        assert o.monto_cuota_dia_1 == Dinero(1_000_000)
        assert o.monto_cuota_dia_2 == Dinero(1_000_000)
        assert o.dia_pago_1 == 15
        assert o.dia_pago_2 == 30
        assert o.deuda_inicial == Dinero(0)
        assert o.fecha_deuda_inicial == datetime.date(2026, 1, 1)
        assert o.activa is True

    def test_sin_cuota_dia_2_es_valido(self) -> None:
        o = _obligacion(monto_cuota_dia_2=None, dia_pago_2=None)
        from garay.dominio.conciliacion.entidades import ObligacionHotel

        assert isinstance(o, ObligacionHotel)
        assert o.monto_cuota_dia_2 is None  # type: ignore[union-attr]
        assert o.dia_pago_2 is None  # type: ignore[union-attr]

    def test_activa_por_defecto(self) -> None:
        from garay.dominio.conciliacion.entidades import ObligacionHotel

        o = ObligacionHotel(
            id=uuid.uuid4(),
            punto_de_venta_nombre="Hostal Dora",
            receptor_nombre="Waldy",
            monto_cuota_dia_1=Dinero(400_000),
            monto_cuota_dia_2=None,
            dia_pago_1=15,
            dia_pago_2=None,
            deuda_inicial=Dinero(2_400_000),
            fecha_deuda_inicial=datetime.date(2026, 1, 1),
        )
        assert o.activa is True

    def test_identidad_por_id(self) -> None:
        oid = uuid.uuid4()
        a = _obligacion(id=oid, punto_de_venta_nombre="Hotel Marie")
        b = _obligacion(id=oid, punto_de_venta_nombre="Otro Hotel")
        assert a == b
        assert hash(a) == hash(b)

    def test_distintos_ids_no_son_iguales(self) -> None:
        a = _obligacion()
        b = _obligacion()
        assert a != b


# ---------------------------------------------------------------------------
# Tests — Egreso.obligacion_hotel_id field
# ---------------------------------------------------------------------------


class TestEgresoObligacionHotelId:
    def test_egreso_tiene_obligacion_hotel_id_none_por_defecto(self) -> None:
        from garay.dominio.conciliacion.entidades import Egreso

        e = Egreso(
            id=uuid.uuid4(),
            descripcion="Cuota hotel",
            monto=Dinero(1_000_000),
            fecha=datetime.date(2026, 9, 15),
            categoria="cuota_hotel",
        )
        assert e.obligacion_hotel_id is None

    def test_egreso_acepta_obligacion_hotel_id(self) -> None:
        from garay.dominio.conciliacion.entidades import Egreso

        hotel_id = uuid.uuid4()
        e = Egreso(
            id=uuid.uuid4(),
            descripcion="Cuota hotel",
            monto=Dinero(1_000_000),
            fecha=datetime.date(2026, 9, 15),
            categoria="cuota_hotel",
            obligacion_hotel_id=hotel_id,
        )
        assert e.obligacion_hotel_id == hotel_id
