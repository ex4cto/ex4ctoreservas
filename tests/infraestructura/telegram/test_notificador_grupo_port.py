"""Tests for NotificadorGrupo port return type: notificar() must return int | None.

TDD RED: written first; fails until the port signature is updated to return
int | None and the FakeNotificadorGrupo honours that contract.
"""

from __future__ import annotations

from garay.dominio.puertos.servicios_externos import NotificadorGrupo


class FakeNotificadorGrupo(NotificadorGrupo):
    """Test double that returns a configurable int | None from notificar()."""

    def __init__(self, return_value: int | None = None) -> None:
        self._return_value = return_value
        self.calls: list[tuple[str, str]] = []

    def notificar(self, mensaje: str, grupo_id: str) -> int | None:
        self.calls.append((mensaje, grupo_id))
        return self._return_value


class TestNotificadorGrupoPortReturnType:
    def test_notificar_devuelve_int_cuando_hay_message_id(self) -> None:
        """notificar() should return the message_id integer when available."""
        fake = FakeNotificadorGrupo(return_value=12345)
        result = fake.notificar("hola", "-100123456")
        assert result == 12345

    def test_notificar_devuelve_none_en_ausencia_de_id(self) -> None:
        """notificar() should return None when no message_id is available."""
        fake = FakeNotificadorGrupo(return_value=None)
        result = fake.notificar("hola", "-100123456")
        assert result is None

    def test_return_value_puede_descartarse(self) -> None:
        """Callers that discard the return value still compile (backward-compat check)."""
        fake = FakeNotificadorGrupo(return_value=99)
        # Intentionally discarding return value — must not raise
        fake.notificar("hola", "-100123456")
        assert len(fake.calls) == 1

    def test_port_abstractmethod_signature_returns_int_or_none(self) -> None:
        """The port's abstract method must declare return type int | None (not None)."""
        hints: dict[str, object] = {}
        for klass in type.mro(NotificadorGrupo):
            if "notificar" in klass.__dict__:
                hints = klass.__dict__["notificar"].__annotations__
                break
        # return annotation must NOT be the bare string "None" — it must include int
        return_ann = hints.get("return")
        assert return_ann is not None, "notificar must have a return type annotation"
        # With `from __future__ import annotations`, annotations are strings.
        # The plain "-> None" annotation stores as the string "None".
        # We require it to include "int" (e.g. "int | None").
        assert "int" in str(return_ann), (
            f"notificar return type is '{return_ann}' — must be 'int | None'"
        )
