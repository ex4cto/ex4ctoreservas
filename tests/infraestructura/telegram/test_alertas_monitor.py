"""Tests for construir_alerta_renovacion — pure Spanish HTML alert builder.

Covers AC-8 (content snapshot) and AC-9 (HTML-escaping).
No mocks: the function is pure (no I/O).
"""

from __future__ import annotations

import datetime

from garay.infraestructura.telegram.alertas_monitor import construir_alerta_renovacion


class TestConstruirAlertaRenovacion:
    def test_snapshot_contiene_dias_fecha_nombre(self) -> None:
        """AC-8: output contains dias, fecha ISO, and service name."""
        resultado = construir_alerta_renovacion(
            nombre="Dominio garaytours.com",
            dias=30,
            fecha=datetime.date(2027, 3, 15),
        )
        assert "30" in resultado
        assert "2027-03-15" in resultado
        assert "garaytours.com" in resultado

    def test_html_escaping_caracteres_peligrosos(self) -> None:
        """AC-9: < and & in nombre are HTML-escaped."""
        resultado = construir_alerta_renovacion(
            nombre="Dominio <test> & co",
            dias=7,
            fecha=datetime.date(2027, 3, 8),
        )
        assert "&lt;test&gt;" in resultado
        assert "&amp;" in resultado
        assert "<test>" not in resultado
        assert " & " not in resultado
