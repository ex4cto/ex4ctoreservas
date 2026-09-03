"""Tests for PropuestaContexto — domain value object for proposals."""

from __future__ import annotations

from garay.dominio.propuestas.contexto import PropuestaContexto


def test_guarda_nombre_empresa() -> None:
    ctx = PropuestaContexto(empresa_nombre="Acme S.A.S.")
    assert ctx.empresa_nombre == "Acme S.A.S."


def test_igualdad_por_valor() -> None:
    assert PropuestaContexto(empresa_nombre="X") == PropuestaContexto(empresa_nombre="X")


def test_es_inmutable() -> None:
    ctx = PropuestaContexto(empresa_nombre="X")
    try:
        ctx.empresa_nombre = "Y"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("PropuestaContexto debería ser inmutable (frozen)")
