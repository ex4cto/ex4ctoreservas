"""Tests for task 1.6: referido_nombre -> referido_alias rename in Participantes."""

from __future__ import annotations

import pytest

from garay.dominio.ventas.valor_objetos import Participantes


class TestParticipantesReferidoAlias:
    def test_referido_alias_field_exists(self) -> None:
        """Task 1.6: Participantes must have referido_alias field."""
        p = Participantes(referido_alias="taxi")
        assert p.referido_alias == "taxi"

    def test_referido_alias_defaults_none(self) -> None:
        p = Participantes()
        assert p.referido_alias is None

    def test_referido_nombre_does_not_exist(self) -> None:
        """Task 1.6: old referido_nombre field must NOT exist."""
        p = Participantes()
        assert not hasattr(p, "referido_nombre"), (
            "referido_nombre debe haber sido renombrado a referido_alias"
        )

    def test_constructing_with_referido_nombre_raises(self) -> None:
        """Task 1.6: passing referido_nombre keyword to Participantes must fail."""
        with pytest.raises(TypeError):
            Participantes(referido_nombre="taxi")  # type: ignore[call-arg]
