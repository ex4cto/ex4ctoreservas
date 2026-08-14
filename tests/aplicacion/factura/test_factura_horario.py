"""Tests for GenerarFacturaService — schedule (horario) row rendering.

RED phase: tests must FAIL before the Horario row is implemented in servicio.py.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from garay.aplicacion.factura.servicio import GenerarFacturaService
from garay.dominio.ventas.contexto import ContextoVenta


def _ctx(
    *,
    destinos_numeros: list[int] | None = None,
    destinos_nombres: list[str] | None = None,
    horarios_por_servicio: dict[int, str] | None = None,
) -> ContextoVenta:
    ctx = ContextoVenta()
    ctx.destinos_numeros = destinos_numeros or [3]
    ctx.destinos_nombres = destinos_nombres or ["Islas"]
    ctx.horarios_por_servicio = horarios_por_servicio if horarios_por_servicio is not None else {}
    ctx.valor = Decimal("500000")
    return ctx


_VID = uuid.uuid4()
_SVC = GenerarFacturaService()


class TestFacturaHorarioRow:
    def test_single_tour_with_schedule_contains_horario_row(self) -> None:
        """horarios_por_servicio={3: '19:00'} → HTML contains 'Horario' and '7:00 PM'."""
        ctx = _ctx(horarios_por_servicio={3: "19:00"})
        html = _SVC.generar(ctx, _VID)

        assert "<td>Horario</td>" in html or "Horario</td>" in html
        assert "7:00 PM" in html

    def test_horario_row_after_fecha_del_tour(self) -> None:
        """The Horario row must appear AFTER the Fecha del tour row in the HTML."""
        ctx = _ctx(horarios_por_servicio={3: "19:00"})
        html = _SVC.generar(ctx, _VID)

        fecha_pos = html.find("Fecha del tour")
        horario_pos = html.find("Horario")
        assert fecha_pos != -1, "Fecha del tour row must be present"
        assert horario_pos != -1, "Horario row must be present"
        assert horario_pos > fecha_pos, "Horario row must appear after Fecha del tour"

    def test_single_tour_morning_schedule(self) -> None:
        """horarios_por_servicio={3: '07:00'} → '7:00 AM' in HTML."""
        ctx = _ctx(
            destinos_numeros=[3],
            destinos_nombres=["Islas"],
            horarios_por_servicio={3: "07:00"},
        )
        html = _SVC.generar(ctx, _VID)
        assert "7:00 AM" in html

    def test_multi_tour_compact_cell(self) -> None:
        """Two tours with schedules → 'Islas 7:00 AM, Chivas 9:00 PM' in the cell."""
        ctx = _ctx(
            destinos_numeros=[3, 7],
            destinos_nombres=["Islas", "Chivas"],
            horarios_por_servicio={3: "07:00", 7: "21:00"},
        )
        html = _SVC.generar(ctx, _VID)
        assert "Islas 7:00 AM, Chivas 9:00 PM" in html

    def test_no_schedule_no_horario_row(self) -> None:
        """horarios_por_servicio={} → NO 'Horario' row in HTML (regression guard)."""
        ctx = _ctx(horarios_por_servicio={})
        html = _SVC.generar(ctx, _VID)
        assert "Horario" not in html

    def test_no_schedule_output_byte_identical_reference(self) -> None:
        """Two identical contexts without schedule must produce the same HTML."""
        ctx1 = _ctx(horarios_por_servicio={})
        ctx2 = _ctx(horarios_por_servicio={})
        html1 = _SVC.generar(ctx1, _VID)
        html2 = _SVC.generar(ctx2, _VID)
        assert html1 == html2

    def test_raw_24h_not_emitted_in_html(self) -> None:
        """Canonical '19:00' must not appear in the HTML output."""
        ctx = _ctx(horarios_por_servicio={3: "19:00"})
        html = _SVC.generar(ctx, _VID)
        assert "19:00" not in html
