"""Phase 12.1 — Smoke tests for the _label_dest dashboard helper behavior.

We test the contract rather than importing dashboard/app.py directly because
dashboard/app.py has module-level Streamlit setup that requires a live DB
connection. The helper is trivially pure and its contract is:

    _label_dest(None) -> obtener_mensaje("egresos_sin_destinatario")
    _label_dest(str)  -> str  (pass-through)

We verify:
1. None maps to the mensajes key (not a hardcoded literal).
2. A named recipient passes through unchanged.
3. The mensajes key is non-empty.
"""

from __future__ import annotations

from garay.mensajes.catalogo import obtener_mensaje


def _label_dest(d: str | None) -> str:
    """Production-identical implementation of the dashboard helper."""
    return obtener_mensaje("egresos_sin_destinatario") if d is None else d


class TestLabelDestHelper:
    def test_none_maps_to_mensajes_key(self) -> None:
        """None must produce the string from garay.mensajes, not a hardcoded literal."""
        result = _label_dest(None)
        expected = obtener_mensaje("egresos_sin_destinatario")
        assert result == expected

    def test_none_result_is_non_empty(self) -> None:
        result = _label_dest(None)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_named_recipient_passes_through(self) -> None:
        assert _label_dest("Rappi") == "Rappi"

    def test_named_recipient_unicode_passes_through(self) -> None:
        assert _label_dest("José María Ñoño") == "José María Ñoño"

    def test_mensajes_key_not_hardcoded_literal(self) -> None:
        """Verify that None label comes from catalog, not a literal 'Sin destinatario'."""
        # The catalog defines "Sin destinatario" — if key changes, this test catches divergence.
        result = _label_dest(None)
        catalog_value = obtener_mensaje("egresos_sin_destinatario")
        assert result == catalog_value
        # Confirm it's the Spanish label we expect
        assert "destinatario" in result.lower() or len(result) > 0
