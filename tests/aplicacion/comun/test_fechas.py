"""Unit tests for the compact per-tour date formatter (Slice 3 — display)."""

from __future__ import annotations

import datetime

from garay.aplicacion.comun.fechas import formatear_fechas_compactas


class TestFormatearFechasCompactas:
    def test_single_pair(self) -> None:
        """One (nombre, datetime) pair renders as 'nombre DD/MM HH:MM'."""
        pares = [("Islas del Rosario", datetime.datetime(2025, 8, 12, 8, 0))]
        assert formatear_fechas_compactas(pares) == "Islas del Rosario 12/08 08:00"

    def test_two_pairs_joined_by_comma_space(self) -> None:
        """Two pairs joined by ', ' in the given order."""
        pares = [
            ("Islas del Rosario", datetime.datetime(2025, 8, 12, 8, 0)),
            ("Bahía Rumbera", datetime.datetime(2025, 8, 12, 19, 0)),
        ]
        assert (
            formatear_fechas_compactas(pares)
            == "Islas del Rosario 12/08 08:00, Bahía Rumbera 12/08 19:00"
        )

    def test_three_pairs_preserve_order(self) -> None:
        """Three pairs preserve the supplied order (deterministic)."""
        pares = [
            ("A", datetime.datetime(2025, 1, 3, 9, 30)),
            ("B", datetime.datetime(2025, 2, 4, 10, 0)),
            ("C", datetime.datetime(2025, 3, 5, 22, 15)),
        ]
        assert (
            formatear_fechas_compactas(pares)
            == "A 03/01 09:30, B 04/02 10:00, C 05/03 22:15"
        )

    def test_empty_returns_empty_string(self) -> None:
        """No pairs → empty string."""
        assert formatear_fechas_compactas([]) == ""
