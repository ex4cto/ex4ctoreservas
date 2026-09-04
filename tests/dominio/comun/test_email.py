"""Tests for shared email normalization/validation."""

from __future__ import annotations

from garay.dominio.comun.email import es_email_valido, normalizar_email


def test_normaliza_espacios_y_mayusculas() -> None:
    assert normalizar_email("Anais. Vignon. 5@Gmail.com") == "anais.vignon.5@gmail.com"


def test_normaliza_recorta_bordes() -> None:
    assert normalizar_email("  Juan@Example.COM  ") == "juan@example.com"


def test_valido_true() -> None:
    assert es_email_valido("juan@example.com") is True
    assert es_email_valido("a.b@mail.ex4cto.co") is True


def test_valido_false() -> None:
    assert es_email_valido("juan@localhost") is False  # sin punto en dominio
    assert es_email_valido("juan example@x.com") is False  # espacio
    assert es_email_valido("sin-arroba.com") is False
    assert es_email_valido("") is False


def test_normalizar_luego_validar_corrige_gap() -> None:
    # El caso real: con espacios no valida; normalizado sí.
    crudo = "Anais. Vignon. 5@gmail.com"
    assert es_email_valido(crudo) is False
    assert es_email_valido(normalizar_email(crudo)) is True
