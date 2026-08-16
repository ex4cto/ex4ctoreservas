"""Tests for construir_alerta_costo_railway — Spanish HTML alert builder.

TDD RED phase: tests written before implementation.

Covers:
- Message contains the costo_actual formatted to 2 decimals
- Message contains the umbral formatted to 0 decimals
- Message contains the estimado_factura formatted to 2 decimals
- HTML special chars in numeric values are safe (e.g. & in a hypothetical context)
- Short plain Spanish text (spot-check key words)
- Returns a str (HTML-safe, parse_mode=HTML compatible)
"""

from __future__ import annotations

from garay.infraestructura.telegram.alertas_monitor import construir_alerta_costo_railway

# ---------------------------------------------------------------------------
# Basic content tests
# ---------------------------------------------------------------------------


def test_alerta_costo_railway_contiene_costo_actual() -> None:
    """Alert message includes the actual month-to-date cost formatted to 2 decimals."""
    msg = construir_alerta_costo_railway(
        costo_actual=15.75,
        umbral=10.0,
        estimado_factura=22.50,
    )
    assert "15.75" in msg


def test_alerta_costo_railway_contiene_umbral() -> None:
    """Alert message includes the threshold (formatted, whole number or 1 decimal)."""
    msg = construir_alerta_costo_railway(
        costo_actual=15.75,
        umbral=10.0,
        estimado_factura=22.50,
    )
    # umbral=10 → should appear as 10 or $10
    assert "10" in msg


def test_alerta_costo_railway_contiene_estimado() -> None:
    """Alert message includes the estimated end-of-month bill formatted to 2 decimals."""
    msg = construir_alerta_costo_railway(
        costo_actual=15.75,
        umbral=10.0,
        estimado_factura=22.50,
    )
    assert "22.50" in msg


def test_alerta_costo_railway_returns_str() -> None:
    """Return type is str."""
    result = construir_alerta_costo_railway(
        costo_actual=5.0,
        umbral=10.0,
        estimado_factura=7.0,
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Spanish language spot-check
# ---------------------------------------------------------------------------


def test_alerta_costo_railway_contiene_texto_espanol() -> None:
    """Alert uses short plain Spanish — checks for key Spanish words."""
    msg = construir_alerta_costo_railway(
        costo_actual=15.75,
        umbral=10.0,
        estimado_factura=22.50,
    )
    # Must mention Railway in some form and use Spanish warning indicator
    assert "Railway" in msg or "railway" in msg.lower()
    # Should mention the month or the threshold being crossed
    lower = msg.lower()
    keywords = ["mes", "límite", "limite", "umbral", "cruzaste", "llevas"]
    assert any(word in lower for word in keywords)


# ---------------------------------------------------------------------------
# HTML safety
# ---------------------------------------------------------------------------


def test_alerta_costo_railway_html_safe_with_decimal_values() -> None:
    """Numeric values with decimals do not introduce unescaped HTML chars."""
    msg = construir_alerta_costo_railway(
        costo_actual=1.23,
        umbral=5.0,
        estimado_factura=9.99,
    )
    # The message should be valid as-is for Telegram HTML parse_mode.
    # Numbers cannot contain HTML-special chars, but we verify no raw & or < leaks.
    # (Full HTML validation is out of scope; we spot-check the dangerous chars.)
    assert "&amp;" not in msg or "&" not in msg.replace("&amp;", "")
    # No unescaped < or > outside of tags
    stripped = msg.replace("<b>", "").replace("</b>", "")
    assert "<" not in stripped and ">" not in stripped


# ---------------------------------------------------------------------------
# Triangulation: different values produce different messages
# ---------------------------------------------------------------------------


def test_alerta_costo_railway_distinto_costo_produce_distinto_mensaje() -> None:
    """Different costo_actual values produce different messages."""
    msg_a = construir_alerta_costo_railway(costo_actual=5.00, umbral=3.0, estimado_factura=8.0)
    msg_b = construir_alerta_costo_railway(costo_actual=9.99, umbral=3.0, estimado_factura=8.0)
    assert msg_a != msg_b


def test_alerta_costo_railway_costo_con_muchos_decimales_trunca_a_dos() -> None:
    """costo_actual with many decimals is rendered to exactly 2 decimal places."""
    msg = construir_alerta_costo_railway(
        costo_actual=3.14159,
        umbral=2.0,
        estimado_factura=5.0,
    )
    # 3.14 should appear, not 3.14159
    assert "3.14" in msg
    assert "3.14159" not in msg


def test_alerta_costo_railway_estimado_con_muchos_decimales_trunca_a_dos() -> None:
    """estimado_factura with many decimals is rendered to exactly 2 decimal places."""
    msg = construir_alerta_costo_railway(
        costo_actual=5.0,
        umbral=3.0,
        estimado_factura=12.99999,
    )
    assert "13.00" in msg
    assert "12.99999" not in msg
