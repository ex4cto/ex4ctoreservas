"""Tests for construir_alerta_cuota — Resend quota HTML alert builder.

TDD RED phase: fails with ImportError until the function is added.
"""

from __future__ import annotations

from garay.infraestructura.telegram.alertas_monitor import construir_alerta_cuota


class TestConstruirAlertaCuotaMensual:
    def test_snapshot_mensual_contiene_datos_clave(self) -> None:
        """Monthly alert contains conteo, cap, umbral, and percentage."""
        resultado = construir_alerta_cuota(
            tipo="mensual",
            conteo=2700,
            cap=3000,
            umbral=2700,
        )
        assert "2700" in resultado
        assert "3000" in resultado
        # Percentage: 2700/3000 = 90%
        assert "90" in resultado

    def test_snapshot_mensual_contiene_texto_legible(self) -> None:
        """Monthly alert is readable plain Spanish mentioning 'correos' and 'mes'."""
        resultado = construir_alerta_cuota(
            tipo="mensual",
            conteo=1500,
            cap=3000,
            umbral=1500,
        )
        texto = resultado.lower()
        assert "correo" in texto or "email" in texto or "Resend" in resultado
        assert "mes" in resultado.lower()

    def test_snapshot_diario_contiene_datos_clave(self) -> None:
        """Daily alert contains conteo and cap."""
        resultado = construir_alerta_cuota(
            tipo="diario",
            conteo=80,
            cap=100,
            umbral=80,
        )
        assert "80" in resultado
        assert "100" in resultado

    def test_snapshot_diario_menciona_dia(self) -> None:
        """Daily alert text refers to 'día' or 'diario'."""
        resultado = construir_alerta_cuota(
            tipo="diario",
            conteo=80,
            cap=100,
            umbral=80,
        )
        texto = resultado.lower()
        assert "día" in texto or "diario" in texto or "ayer" in texto

    def test_html_escape_en_tipo(self) -> None:
        """tipo value is not raw HTML (no injection; tipo is internal but we confirm no crash)."""
        # tipo is always "mensual" or "diario" in practice, but the function must not crash
        resultado = construir_alerta_cuota(
            tipo="mensual",
            conteo=100,
            cap=3000,
            umbral=100,
        )
        assert isinstance(resultado, str)
        assert len(resultado) > 0

    def test_html_escape_seguridad_valores(self) -> None:
        """Values with special HTML chars in context: function returns valid HTML fragment."""
        # cap and conteo are always ints — no HTML escape needed for numbers.
        # Just confirm the return is a string with the expected HTML bold tag.
        resultado = construir_alerta_cuota(
            tipo="mensual",
            conteo=2850,
            cap=3000,
            umbral=2850,
        )
        # Must include a bold tag (mirrors construir_alerta_renovacion style)
        assert "<b>" in resultado

    def test_porcentaje_redondeado_mensual(self) -> None:
        """Percentage is integer-rounded for the monthly alert."""
        resultado = construir_alerta_cuota(
            tipo="mensual",
            conteo=1000,
            cap=3000,
            umbral=1000,
        )
        # 1000/3000 = 33.33... → "33" in output
        assert "33" in resultado
