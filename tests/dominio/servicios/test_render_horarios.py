"""Unit tests for render_horarios — pure domain helper.

RED phase: all tests must FAIL before the implementation exists in horarios.py.
"""

from __future__ import annotations

from garay.dominio.servicios.horarios import render_horarios


class TestRenderHorarios:
    def test_empty_list_returns_none(self) -> None:
        assert render_horarios([]) is None

    def test_single_tour_with_schedule_returns_display_only(self) -> None:
        """Single non-empty pair → formatted time only, no tour name."""
        result = render_horarios([("Islas", "19:00")])
        assert result == "7:00 PM"

    def test_multi_tour_compact_format(self) -> None:
        """Multiple non-empty pairs → 'name HH:MM AP, name HH:MM AP'."""
        result = render_horarios([("Islas", "07:00"), ("Chivas", "21:00")])
        assert result == "Islas 7:00 AM, Chivas 9:00 PM"

    def test_partial_list_empty_entry_filtered_single_survivor(self) -> None:
        """One empty, one non-empty → single survivor collapses to scalar (no name)."""
        result = render_horarios([("Islas", ""), ("Chivas", "21:00")])
        assert result == "9:00 PM"

    def test_all_empty_horarios_returns_none(self) -> None:
        """All pairs with empty horario → None."""
        assert render_horarios([("Islas", ""), ("Chivas", "")]) is None

    def test_midnight_edge_case(self) -> None:
        result = render_horarios([("X", "00:00")])
        assert result == "12:00 AM"

    def test_noon_edge_case(self) -> None:
        result = render_horarios([("X", "12:00")])
        assert result == "12:00 PM"

    def test_raw_24h_string_never_emitted(self) -> None:
        """The canonical 24h string must NOT appear in output."""
        result = render_horarios([("Islas", "19:00")])
        assert result is not None
        assert "19:00" not in result

    def test_multi_tour_no_name_in_single_survivor(self) -> None:
        """When filtering leaves a single survivor, the name is dropped."""
        result = render_horarios([("Tour A", ""), ("Tour B", "14:30")])
        assert result == "2:30 PM"
        assert "Tour B" not in result
