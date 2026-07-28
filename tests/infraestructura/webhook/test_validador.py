"""Tests for webhook secret validator — TDD RED→GREEN phase."""

from __future__ import annotations

import pytest

from garay.infraestructura.webhook.validador import ErrorSecretInvalido, validar_secret


def test_secret_correcto_pasa() -> None:
    # Should not raise
    validar_secret("mi-secreto-super-seguro", expected="mi-secreto-super-seguro")


def test_secret_incorrecto_lanza_error() -> None:
    with pytest.raises(ErrorSecretInvalido, match="Secret invalido"):
        validar_secret("incorrecto", expected="correcto")


def test_secret_vacio_lanza_error() -> None:
    with pytest.raises(ErrorSecretInvalido):
        validar_secret("", expected="correcto")
