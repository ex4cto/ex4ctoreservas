"""Tests for _construir_resumen date rendering (Slice 3 — display).

Single-tour keeps the byte-identical '%d/%m/%Y' rendering; multi-tour renders
the compact 'nombre DD/MM HH:MM' string joined by ', ' in destinos_numeros order.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta

SERVICIOS: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
    (1, "Islas del Rosario", Decimal("100000"), Decimal("50000"), "ISLAS"),
    (2, "Bahía Rumbera", Decimal("150000"), None, "ISLAS"),
    (3, "City Tour", None, None, "CITY"),
]
PUNTOS: list[str] = ["Marie Real"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS, puntos_venta=PUNTOS)


class TestResumenSingleTourParity:
    def test_single_tour_renders_date_only(self, fsm: FSMTiquetera) -> None:
        """One tour → '%d/%m/%Y', no name and no hour (byte-identical parity)."""
        ctx = ContextoVenta(
            destinos_numeros=[1],
            destinos_nombres=["Islas del Rosario"],
            fecha_salida=datetime.datetime(2025, 8, 12, 8, 0),
            fechas_por_servicio={1: datetime.datetime(2025, 8, 12, 8, 0)},
        )
        resumen = fsm._construir_resumen(ctx)
        assert "12/08/2025" in resumen
        # No compact multi-tour marker: the single date must not carry a name+hour.
        assert "Islas del Rosario 12/08 08:00" not in resumen

    def test_single_tour_no_fechas_por_servicio_still_date_only(
        self, fsm: FSMTiquetera
    ) -> None:
        """One tour with empty map → still scalar '%d/%m/%Y'."""
        ctx = ContextoVenta(
            destinos_numeros=[1],
            destinos_nombres=["Islas del Rosario"],
            fecha_salida=datetime.datetime(2025, 8, 12),
            fechas_por_servicio={},
        )
        resumen = fsm._construir_resumen(ctx)
        assert "12/08/2025" in resumen


class TestResumenMultiTourCompact:
    def test_two_tours_compact_string(self, fsm: FSMTiquetera) -> None:
        """Two tours → 'nombre DD/MM HH:MM, nombre DD/MM HH:MM' in order."""
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Islas del Rosario", "Bahía Rumbera"],
            fecha_salida=datetime.datetime(2025, 8, 12, 8, 0),
            fechas_por_servicio={
                1: datetime.datetime(2025, 8, 12, 8, 0),
                2: datetime.datetime(2025, 8, 12, 19, 0),
            },
        )
        resumen = fsm._construir_resumen(ctx)
        assert (
            "Islas del Rosario 12/08 08:00, Bahía Rumbera 12/08 19:00" in resumen
        )

    def test_three_tours_compact_string_in_order(self, fsm: FSMTiquetera) -> None:
        """Three tours render in destinos_numeros order."""
        ctx = ContextoVenta(
            destinos_numeros=[1, 2, 3],
            destinos_nombres=["Islas del Rosario", "Bahía Rumbera", "City Tour"],
            fecha_salida=datetime.datetime(2025, 8, 10, 9, 0),
            fechas_por_servicio={
                1: datetime.datetime(2025, 8, 12, 8, 0),
                2: datetime.datetime(2025, 8, 12, 19, 0),
                3: datetime.datetime(2025, 8, 10, 9, 0),
            },
        )
        resumen = fsm._construir_resumen(ctx)
        assert (
            "Islas del Rosario 12/08 08:00, "
            "Bahía Rumbera 12/08 19:00, "
            "City Tour 10/08 09:00" in resumen
        )

    def test_multi_tour_missing_entry_falls_back_to_scalar(
        self, fsm: FSMTiquetera
    ) -> None:
        """If a tour date is missing from the map, fall back to the scalar for it."""
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Islas del Rosario", "Bahía Rumbera"],
            fecha_salida=datetime.datetime(2025, 8, 12, 8, 0),
            fechas_por_servicio={1: datetime.datetime(2025, 8, 12, 8, 0)},
        )
        resumen = fsm._construir_resumen(ctx)
        # Tour 1 uses its own date; tour 2 falls back to fecha_salida scalar.
        assert "Islas del Rosario 12/08 08:00" in resumen
        assert "Bahía Rumbera 12/08 08:00" in resumen

    def test_multi_tour_empty_fechas_degrades_to_scalar(
        self, fsm: FSMTiquetera
    ) -> None:
        """Two tours with fechas_por_servicio={} must degrade to scalar DD/MM/YYYY,
        not render '00:00' midnight artifacts from a dict-miss fallback."""
        ctx = ContextoVenta(
            destinos_numeros=[1, 2],
            destinos_nombres=["Islas del Rosario", "Bahía Rumbera"],
            fecha_salida=datetime.datetime(2025, 8, 12, 8, 0),
            fechas_por_servicio={},
        )
        resumen = fsm._construir_resumen(ctx)
        assert "12/08/2025" in resumen
        assert "00:00" not in resumen
