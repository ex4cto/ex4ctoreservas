"""Tests for FSMTiquetera._construir_resumen — schedule (horario) line.

RED phase: tests must FAIL before the horario line is implemented in fsm.py.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from garay.aplicacion.tiquetera.fsm import FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta

SERVICIOS: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (3, "Islas del Rosario", Decimal("100000"), Decimal("50000"), "ISLAS", []),
    (7, "Chivas", Decimal("150000"), None, "ISLAS", []),
]
PUNTOS: list[str] = ["Marie Real"]


def _fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS, puntos_venta=PUNTOS)


def _ctx_with_schedule(horarios: dict[int, str]) -> ContextoVenta:
    return ContextoVenta(
        destinos_numeros=[3],
        destinos_nombres=["Islas del Rosario"],
        fecha_salida=datetime.datetime(2026, 9, 20, 8, 0),
        fechas_por_servicio={3: datetime.datetime(2026, 9, 20, 8, 0)},
        horarios_por_servicio=horarios,
    )


def _ctx_without_schedule() -> ContextoVenta:
    return ContextoVenta(
        destinos_numeros=[3],
        destinos_nombres=["Islas del Rosario"],
        fecha_salida=datetime.datetime(2026, 9, 20, 8, 0),
        fechas_por_servicio={3: datetime.datetime(2026, 9, 20, 8, 0)},
        horarios_por_servicio={},
    )


class TestResumenHorarioLine:
    def test_with_schedule_contains_am_pm_display(self) -> None:
        """horarios_por_servicio={3: '19:00'} → resumen contains '7:00 PM'."""
        fsm = _fsm()
        ctx = _ctx_with_schedule({3: "19:00"})

        result = fsm._construir_resumen(ctx)

        assert "7:00 PM" in result

    def test_with_schedule_horario_after_fecha_salida(self) -> None:
        """The Horario line must appear after the Fecha salida line."""
        fsm = _fsm()
        ctx = _ctx_with_schedule({3: "19:00"})

        result = fsm._construir_resumen(ctx)

        fecha_pos = result.find("Fecha salida:")
        horario_pos = result.find("Horario:")
        assert fecha_pos != -1, "Fecha salida must be in resumen"
        assert horario_pos != -1, "Horario must be in resumen with schedule"
        assert horario_pos > fecha_pos

    def test_no_schedule_no_horario_line(self) -> None:
        """horarios_por_servicio={} → resumen contains NO 'Horario' text."""
        fsm = _fsm()
        ctx = _ctx_without_schedule()

        result = fsm._construir_resumen(ctx)

        assert "Horario" not in result

    def test_no_schedule_no_blank_line_at_horario_position(self) -> None:
        """Owner constraint: no blank line where horario would have been (no '\\n\\n')."""
        fsm = _fsm()
        ctx = _ctx_without_schedule()

        result = fsm._construir_resumen(ctx)

        # Find position of Fecha salida, check that directly after the newline
        # there is no additional newline (i.e. no \n\n at the horario injection point)
        lines = result.splitlines()
        fecha_idx = next((i for i, line in enumerate(lines) if "Fecha salida:" in line), None)
        assert fecha_idx is not None

        # After "Fecha salida: ..." line, the next line must NOT be blank
        # (blank = index out of bounds or non-empty content)
        if fecha_idx + 1 < len(lines):
            next_line = lines[fecha_idx + 1]
            assert next_line.strip() != "", (
                f"Blank line found after Fecha salida when no schedule: {result!r}"
            )

    def test_no_schedule_byte_identical_to_baseline(self) -> None:
        """Two resumen calls with empty horarios produce identical strings."""
        fsm = _fsm()
        ctx1 = _ctx_without_schedule()
        ctx2 = _ctx_without_schedule()

        r1 = fsm._construir_resumen(ctx1)
        r2 = fsm._construir_resumen(ctx2)

        assert r1 == r2

    def test_raw_24h_not_in_resumen(self) -> None:
        """Canonical '19:00' must not appear in the resumen output."""
        fsm = _fsm()
        ctx = _ctx_with_schedule({3: "19:00"})

        result = fsm._construir_resumen(ctx)

        assert "19:00" not in result
