"""Unit tests for _construir_dm_freelancer pure function.

Spec ref: "DM Content Gate", "DM Format", "No private data in DM".
"""

from __future__ import annotations

from garay.aplicacion.tiquetera.servicio import _construir_dm_freelancer


def test_both_none_returns_none() -> None:
    """Both fields empty/None -> returns None, no DM."""
    assert _construir_dm_freelancer("Tour Test", None, None) is None

def test_whitespace_only_info_tour_returns_none() -> None:
    """Whitespace-only info_tour + None observaciones -> returns None."""
    assert _construir_dm_freelancer("Tour Test", "   ", None) is None

def test_whitespace_only_both_returns_none() -> None:
    """Whitespace-only both fields -> returns None."""
    assert _construir_dm_freelancer("Tour Test", "   ", "  \t ") is None

def test_only_info_tour_contains_name_and_info_no_obs_section() -> None:
    """Only info_tour set -> DM contains name and info text, no obs section."""
    result = _construir_dm_freelancer("Tour Rosario", "Salida 8am", None)
    assert result is not None
    assert "Tour Rosario" in result
    assert "Salida 8am" in result
    assert "Observaciones" not in result

def test_only_observaciones_contains_name_and_obs_section() -> None:
    """Only observaciones set -> DM contains obs section, no empty info section."""
    result = _construir_dm_freelancer("Tour Islas", None, "No apto para embarazadas")
    assert result is not None
    assert "Tour Islas" in result
    assert "Observaciones" in result
    assert "No apto para embarazadas" in result

def test_both_present_full_dm_correct_order() -> None:
    """Both fields set -> full DM with correct section ordering."""
    result = _construir_dm_freelancer(
        "Tour Plancton",
        "Salida 8am, almuerzo incluido",
        "No apto para embarazadas",
    )
    assert result is not None
    assert "Tour Plancton" in result
    assert "Salida 8am, almuerzo incluido" in result
    assert "Observaciones" in result
    assert "No apto para embarazadas" in result
    # info_tour must appear before observaciones section
    info_pos = result.index("Salida 8am")
    obs_pos = result.index("Observaciones")
    assert info_pos < obs_pos

def test_html_special_chars_escaped() -> None:
    """HTML special chars in content are escaped."""
    result = _construir_dm_freelancer(
        "Tour <&>",
        "Info <b>bold</b> & more",
        "Obs <script>",
    )
    assert result is not None
    assert "<b>bold</b>" not in result
    assert "&amp;" in result or "&lt;" in result or "&gt;" in result
    assert "<script>" not in result

def test_tour_name_appears_in_bold_html_tag() -> None:
    """Tour name is wrapped in <b> HTML tag."""
    result = _construir_dm_freelancer("Tour Bahia", "Algo de info", None)
    assert result is not None
    assert "<b>" in result
    assert "Tour Bahia" in result
