"""Tests for detectar_reenvio domain utility — RED phase."""

from __future__ import annotations

import pytest

from garay.dominio.conciliacion.reenvio import detectar_reenvio


@pytest.mark.parametrize(
    "asunto,cuerpo,esperado",
    [
        # Subject-based detection
        ("Fwd: Notificacion bancaria", "", True),
        ("FWD: Notificacion bancaria", "", True),
        ("fwd: algo", "", True),
        ("Fw: Pago recibido", "", True),
        ("FW: Pago recibido", "", True),
        ("fw: otra cosa", "", True),
        ("Rv: Notificacion", "", True),
        ("RV: Notificacion", "", True),
        ("rv: algo mas", "", True),
        # Body-based detection
        ("Notificacion bancaria", "---------- Forwarded message ---------", True),
        ("Notificacion bancaria", "forwarded message from someone", True),
        ("Notificacion bancaria", "FORWARDED MESSAGE", True),
        # Clean — no forward
        ("Notificacion bancaria", "Tu cuenta recibio un pago", False),
        ("Pago exitoso", "Monto: 50000", False),
        # Subject contains but not starts with fwd — still True per spec
        # Note: spec says "starts with or contains" so "contains" wins
        ("Re: fwd: algo", "", True),
    ],
)
def test_detectar_reenvio(asunto: str, cuerpo: str, esperado: bool) -> None:
    assert detectar_reenvio(asunto, cuerpo) == esperado


def test_detectar_reenvio_caso_limpio_sin_argumentos() -> None:
    """Empty subject and body are not a forward."""
    assert detectar_reenvio("", "") is False
